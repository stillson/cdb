#!/usr/bin/env python

import binascii
import functools
import inspect
import io
import time
import traceback
import types
import sys
import string
import exceptions
import collections

from dis import dis
from pprint import pformat as pf
from pprint import pprint as pp

USE_COLOR = True
if USE_COLOR:
# short replacement for termcolor module
    def colorize(string, color=None, bg=None, eff=[None]):
        A= {None: '', 'blink': '\033[5m', 'bold': '\033[1m', 'concealed': '\033[8m',
        'dark': '\033[2m', 'reverse': '\033[7m', 'underline': '\033[4m'}
        B= {None: '', 'blue': '\033[44m', 'cyan': '\033[46m', 'green': '\033[42m',
        'grey': '\033[40m','gray': '\033[40m', 'magenta': '\033[45m', 'red': '\033[41m',
        'white': '\033[47m','yellow': '\033[43m'}
        C={ None:'','black':'\033[30m', 'blue': '\033[34m', 'cyan': '\033[36m', 'green': '\033[32m',
        'grey': '\033[30m','grey': '\033[30m', 'magenta': '\033[35m', 'red': '\033[31m',
        'white': '\033[37m', 'yellow': '\033[33m'}
        return ''.join([C[color], B[bg], ''.join([A[i] for i in eff ]), str(string), '\033[0m'])

    def ecolorize(string, fg=None, bg=None, eff=[None]):
        fg_str = '\033[38;2;{0};{1};{2}m'.format(*fg) if fg else ""
        bg_str = '\033[48;2;{0};{1};{2}m'.format(*bg) if bg else ""
        return colorize( fg_str + bg_str + string, eff=eff)
else:
    def colorize(x, *a, **b): return x
    def ecolorize(x,*a, **b): return x

# uncompyle2 support
try:
    from uncompyle2 import uncompyle
    UC=True
except:
    UC=False
    def uncompyle(*args, **kwargs):
        return 'no uncompyle2 support'

# GLOBALS
NL = '\n'

## type wrangling
SetType = type(set(range(0)))
FrozenSetType = type(frozenset(range(0)))
class A:
    def foo(self): pass

InstanceMethodType = type(A.foo)

SimplePrint     = [ types.IntType,      types.BooleanType, types.StringType,
                    types.FloatType,    types.StringTypes, types.ObjectType,
                    types.EllipsisType, types.LongType,    types.BufferType,
                    types.UnicodeType,  types.ComplexType, types.XRangeType,
                    types.NoneType,]

CodeTypes       = [ types.CodeType,            types.MethodType,        types.FunctionType,
                    types.BuiltinFunctionType, types.BuiltinMethodType, types.LambdaType,
                    InstanceMethodType]

TypeTypes       = [ types.ClassType, types.TypeType]

IterableTypes   = [ types.DictionaryType, types.ListType, types.TupleType, SetType, FrozenSetType]

LessSimpleTypes = [ types.MemberDescriptorType, types.GetSetDescriptorType, types.DictProxyType,
                    types.GeneratorType,        types.FileType,             types.FrameType,
                    types.ModuleType,           types.NotImplementedType,   types.SliceType,
                    types.TracebackType]

BasicColl       = (collections.Container, collections.Set, collections.MutableSet, collections.KeysView, collections.ItemsView,
                   collections.MutableSequence, collections.Sequence)


# not used
OtherTypes      = [ types.InstanceType]

BraceTable = { types.ListType:  '[]',
               types.TupleType: '()',
               SetType:         '{}',
               FrozenSetType:   '{}'}


NoRecurseTypes = SimplePrint + CodeTypes + IterableTypes

# easy color print functions
def col_none(x): return colorize(x, 'black')
def col_time(x): return colorize(x, 'yellow', 'cyan', eff=['bold'])
def col_ind(x):  return colorize(x, 'green')
def col_kw(x):   return colorize(x, 'blue')
def col_simp(x): return colorize(x, 'green')
def col_err(x):  return colorize(x, 'red', 'blue', eff=['blink'])
def col_obj(x):  return colorize(x, 'magenta')
def col_mem(x):  return colorize(x, 'blue')
def col_fun(x):  return colorize(x, 'red')
def col_stk(x):  return colorize(x, 'red')
def col_rpt(x):  return colorize(x, 'blue', 'yellow')
def col_key(x):  return colorize(x, 'green', eff=['bold'])
def col_brc(x):  return colorize(x, eff=['bold'])
def col_tag(x):  return colorize(x, 'yellow', 'blue')


# simple string for the string
def type_str(x):
    if type(x) == types.InstanceType:
        if repr(x)[0] != '<':
            repr_str = str(x.__repr__).split()[2][:-9]
            return '<%s>' % repr_str
        return '<%s>' % repr(x)[1:].split()[0]
    if str(type(x)).startswith('<type'):
        return "<%s>" % str(type(x))[7:-2]
    if str(type(x)).startswith('<class'):
        return "<%s>" % str(type(x))[8:-2]
    return "<%s>" % str(type(x))[1:-2]

# if string not printable, hexlify it
def pstr(x):
    def not_printable(c):
        return not c in string.printable + '\033'
    s = str(x)
    if any(not_printable(i) for i in s):
        return binascii.hexlify(s)
    return s

class Writer(object):
    """
    Writer handles writes to a debugging file. Exists mainly to
    store state (the file name)
    """
    def __init__(self, f_name='/tmp/cdb'):
        self._f_name = f_name

    def write_val(self, *args, **kwargs):
        with open(self._f_name, 'a') as f:
            f.write(col_time(time.strftime("%m.%d %H:%M:%S =>\n")))
            for i, j in enumerate(args):
                f.write(col_ind("  <%d>:" % i))
                f.write(pstr(j) + NL)
            for k, v in kwargs.items():
                f.write(col_kw("  %s=" % k))
                f.write(pstr(v) + NL)
            f.write('\n')

    def write_dump(self, *args, **kwargs):
        with open(self._f_name, 'a') as f:
            f.write(col_time(time.strftime("%m.%d %H:%M:%S =>")))
            for i in args:
                f.write(i)
            for k, v in kwargs.items():
                f.write(k)

                f.write('=>')
                f.write(v)
            f.write('\n')

# context manager to capture stdout of a function
# that print but doesn't return a value.
# written to capture output of dis.dis()
#
# use:
# rv = []
# with CaptureStdout(rv):
#     dis.dis(function)
#
# print rv
class CaptureStdout:
    def __init__(self, output):
        self._out = output
        self.old_stdout = None

    def __enter__(self):
        self.old_stdout = sys.stdout
        sys.stdout = io.BytesIO()

    def __exit__(self, t, v, tb):
        text = sys.stdout.getvalue()
        sys.stdout.close()
        sys.stdout = self.old_stdout
        rv = text.split('\n')
        self._out += rv

# just what it looks like
def indent(i):
    return " " * i

# extended dis. returns output instead of
# just printint it.
def dis_ext(f, indt=0):
    rv = []
    with CaptureStdout(rv):
        dis(f)
    rv = [indent(indt) + j for j in rv]
    return "\n".join(rv)

# extended decompyle
def dec_ext(f, indt=0, showasm=0, showast=0, deob=0):
    rv = []

    with CaptureStdout(rv):
        uncompyle('2.7', f, sys.stdout, showasm=showasm, showast=showast, deob=deob)
    rv = [indent(indt) + j for j in rv]
    return "\n".join(rv)


# wrapper to deal with recursion depth
# also returns on any exception
def depth_dec(f):

    @functools.wraps(f)
    def depth_rfunc(self, obj, inc = True, **kwargs):
        if inc:
            self.depth += 1
        if self.depth > self.max_depth:
            self.depth -= 1
            return col_err('Max Depth!!\n')
        try:
            rv = f(self, obj, **kwargs)
        except:
            return col_err('Exception\n')
        if inc:
            self.depth -= 1
        return rv
    return depth_rfunc

# column width
C_WIDTH = 8
class ObjectDumper(object):
    def __init__(self):
        self.depth = -1
        self.tab_space = 8
        self.subtab = self.tab_space//2
        self.column_width = C_WIDTH
        self.max_depth = 20
        self.cache = set()
        self.deep=2
        self.f_introspect = 0 # set the level of function introspections
        self.all_members = False # set to True to get __* members

    # indent
    @property
    def ind(self):
        #return ("%d" % self.depth) * self.depth * self.tab_space
        return " " * self.depth * self.tab_space

    # sub indent
    @property
    def subi(self):
        #if self.depth % 2 == 0:
        #    return "^" * self.subtab
        return " " * self.subtab

    # full column width
    @property
    def full_col(self):
        d = pstr(self.depth)
        return d * self.column_width

    # put values in a column
    def spacing(self, h_len):
        return " " * ((self.column_width - h_len))

    # get args for a function
    def func_args(self, obj):
        argspec = inspect.getargspec(obj)
        args    = argspec.args     if argspec.args     else ''
        v_args  = argspec.varargs  if argspec.varargs  else ''
        k_args  = argspec.keywords if argspec.keywords else ''

        if args:   args = ', '.join(args)
        if v_args: v_args = ', *%s' % k_args
        if k_args: k_args = ', **%s' % v_args

        return '(%s%s%s)' % (args, k_args, v_args)

    # general function introspection
    def func_info(self, obj, indt=0):
        a = self.f_introspect & 0x1
        b = self.f_introspect & 0x2
        c = self.f_introspect & 0x4
        rv = ''
        try:
            rv += dec_ext(obj.func_code, indt + 4, showasm=a,showast=b,deob=c)
        except:
            rv += dis_ext(obj, indt + 4) + NL

        return rv

    @depth_dec
    def dump_obj(self, obj, offset=C_WIDTH, lead=False, newline=True):
        # determine indent
        ind  = self.ind if not lead else ""
        spc  = self.spacing(offset) if lead else ind
        subi = self.subi
        nl   = NL if newline else ""

        ty = type(obj)

        try:
            if ty not in SimplePrint:
                h = hash(obj)
                if h in self.cache:
                   return spc + col_rpt(pstr(obj)) + NL
                self.cache.add(h)
        except exceptions.TypeError:
            pass

        if ty in SimplePrint:
            return ind + col_simp(type_str(obj) + ":"+ col_none(repr(obj))) + nl

        rv = ind + col_simp(type_str(obj)) + ":"

        # check types

        # object groupings
        if inspect.ismodule(object):
            if self.depth < 2:
                return rv + subi + 'Package:%s\n' % obj.__name__
            else:
                rv += subi + 'Package:%s' % obj.__name__
        if inspect.isabstract(object):
            pass
        # callables
        if inspect.ismethod(object):
            pass
        if inspect.isfunction(object):
            pass
        if inspect.isgeneratorfunction(object):
            pass
        if inspect.isroutine(object):
            pass
        if inspect.isbuiltin(object):
            pass

        # descriptors
        if inspect.ismethoddescriptor(object):
            pass
        if inspect.isdatadescriptor(object):
            pass
        if inspect.ismemberdescriptor(object):
            pass
        if inspect.isgetsetdescriptor(object):
            pass

        # generators
        if inspect.isgenerator(object):
            pass

        # code like
        if inspect.istraceback(object):
            pass
        if inspect.isframe(object):
            pass
        if inspect.iscode(object):
            rv += '%s%s code %s\n' % (ind, obj.func_name, self.func_args(obj))
            return rv

        if isinstance(object, BasicColl):
            brc = BraceTable.get(ty, '<>')
            rv += nl + self.ind + subi + col_brc(brc[0]) + NL
            for v in obj:
                rv += subi + self.dump_obj(v)
            rv += self.ind + subi + col_brc(brc[1]) + NL
            return rv

        if isinstance(object, collections.Iterable):
            pass
        if isinstance(object, collections.Iterator):
            pass
        if isinstance(object, collections.Sized):
            pass
        if isinstance(object, collections.Container):
            pass
        if isinstance(object, collections.Callable):
            pass
        if isinstance(object, collections.Set):
            pass
        if isinstance(object, collections.MutableSet):
            pass
        if isinstance(object, collections.Mapping):
            pass
        if isinstance(object, collections.MutableMapping):
            pass
        if isinstance(object, collections.MappingView):
            pass
        if isinstance(object, collections.KeysView):
            pass
        if isinstance(object, collections.ItemsView):
            pass
        if isinstance(object, collections.ValuesView):
            pass
        if isinstance(object, collections.Sequence):
            pass
        if isinstance(object, collections.MutableSequence):
            pass

        if inspect.isclass(object):
            rv += NL + self.ind + "----------------------" + NL
            members = inspect.getmembers(obj)

            for name, val in members:
                if not self.all_members and name.startswith('__'):
                    continue
                rv += self.ind + subi + col_mem(name) + self.spacing(len(name)) + '=>'
                rv += col_obj(self.dump_obj(val, lead=True))
            rv += self.ind + "----------------------" +NL
            return rv

        #########################
        # methods, functions, etc
        #########################

        if ty in CodeTypes:
            if ty == types.CodeType:
                pass
            elif ty == types.UnboundMethodType:
                try:
                    spec = self.func_args(obj)
                    rv += '%s%s%s unbound method\n' % (ind, obj.im_func.func_name, spec)
                    if self.depth < 2:
                        rv += self.func_info(obj, len(subi)) + NL
                    return rv
                except:
                    try:
                        spec = self.func_args(obj)
                    except:
                        spec = "()"
                    rv += '%s%s%s unbound method2\n' % (ind, obj.im_func.__name__, spec)

                    if self.depth < 2:
                        rv += self.func_info(obj, len(subi)) + NL
                    return rv
            elif ty == InstanceMethodType:
                spec = self.func_args(obj)
                rv += ind + '%s%s\n' % (obj.func_name, spec)

                if self.depth < 2:
                    rv += self.func_info(obj, len(subi)) + NL
                return rv

            elif ty == types.FunctionType:
                # includes LambdaType
                spec = self.func_args(obj)
                rv += ind + '%s%s function\n' % (obj.func_name, spec)

                if self.depth < 2:
                    rv += self.func_info(obj, len(subi)) + NL
                return rv
            elif ty == types.MethodType:
                spec = self.func_args(obj)
                rv +=  ind + '%s%s method\n' % (obj.im_func.func_name, spec)

                if self.depth < 2:
                    rv += self.func_info(obj, len(subi)) + NL

                return rv
            elif ty == types.BuiltinMethodType:
                return rv + '%s%s() builtin method\n' % (ind, obj.__name__)
            elif ty == types.BuiltinFunctionType:
                return rv + ind + '%s <builtin function>\n' % (obj.__name__)

        #######################
        #iterables, containers
        #######################
        if ty in IterableTypes:
            if ty == types.DictionaryType:
                rv += NL + self.ind + subi + col_brc('{') + NL
                for k, v in obj.items():
                    if self.all_members or (hasattr(k,'startswith') and not k.startswith('__')):
                        rv += '%s%s%s<--> %s' % (self.ind + subi,
                                                col_key(pstr(k)),
                                                self.spacing(len(pstr(k))),
                                                self.dump_obj(v, lead=True))
                rv += self.ind + subi + col_brc('}') + NL
                return rv
            elif ty == types.ListType:
                rv += nl + self.ind + subi + col_brc('[') + NL
                for v in obj:
                    rv += subi + self.dump_obj(v)
                rv += self.ind + subi + col_brc(']') + NL
                return rv
            elif ty == types.TupleType:
                rv += nl +self. ind + subi + col_brc('(') + NL
                for v in obj:
                    rv += subi + self.dump_obj(v)
                rv += self.ind + subi + col_brc(')') + NL
                return rv
            elif ty == SetType:
                rv += nl + self.ind + subi + col_brc('set(') + NL
                for v in obj:
                    rv += subi + self.dump_obj(v)
                rv += self.ind + subi + col_brc(')') + NL
                return rv
            elif ty == FrozenSetType:
                rv +=  nl + self.ind + subi + col_brc('frozenset(') + NL
                for v in obj:
                    rv += subi + self.dump_obj(v)
                rv += self.ind + subi + col_brc(')') + NL
                return rv

        # classes/types
        if ty in TypeTypes:
            #print ty
            new_info = {}

            if self.depth < 2:
                for i in inspect.classify_class_attrs(obj):
                    if not i.name.startswith('--'):
                        new_info[i.name] = i.object

                return rv + self.dump_obj(new_info)
            else:
                info = [i.name + ":" + i.kind for i in inspect.classify_class_attrs(obj) if self.all_members or not i.name.startswith('__')]
                return rv + self.dump_obj(info)


        if ty in LessSimpleTypes:
            if ty == types.NotImplementedType:
                return rv + subi + 'NotImplemented\n'
            elif ty == types.DictProxyType:
                return rv + subi + 'dictionary proxy\n'
            elif ty == types.GeneratorType:
                #__name__
                return rv + subi + '<generator>\n'
            elif ty == types.GetSetDescriptorType:
                #__name__
                return rv + subi + '<GetSetDescriptor>\n'
            elif ty == types.ModuleType:
                if self.depth < 2:
                    return rv + subi + 'Package:%s\n' % obj.__name__
                else:
                    rv += subi + 'Package:%s' % obj.__name__
            elif ty == types.FrameType:
                return rv + subi + 'Frame\n'
            elif ty == types.FileType:
                return rv + subi + 'File:%s\n' % obj.name
            elif ty == types.TracebackType:
                return rv + subi +'Traceback\n'
            elif ty == types.MemberDescriptorType:
                #__name__
                return rv + subi + 'MemberDescriptor\n'
            elif ty == types.SliceType:
                return rv + subi + 'Slice%s\n' % repr(obj)

        #default case
        # most likely a class instance
        rv += NL + self.ind + "----------------------" + NL
        members = inspect.getmembers(obj)

        for name, val in members:
            if not self.all_members and name.startswith('__'):
                continue
            rv += self.ind + subi + col_mem(name) + self.spacing(len(name)) + '=>'
            rv += col_obj(self.dump_obj(val, lead=True))
        rv += self.ind + "----------------------" +NL
        return rv

    def dwrap(self, obj):
        self.cache = set([])
        self.depth = -1
        return self.dump_obj(obj)

####################################
#
#  Improved/Simplified clone of q.py
#
####################################

class DBPrinter(object):
    def __init__(self, f_name='/tmp/cdb'):
        self._f_name = f_name
        self.writer = Writer(f_name)
        self.dumper = ObjectDumper()
        self.dumper.max_depth = 3
        self.deep = 1

    # decorator:  mark when function called, args, and return vals
    def cdb_dec(self, f):
        wname = ".".join((f.__module__, f.__name__))
        wname = col_fun('{{%s}}' % wname)

        @functools.wraps(f)
        def cdb_rfunc(*args, **kwargs):
            tag = int(time.time()*10000) % 1000000
            self.writer.write_val(tag, 'in->' + wname, *args, **kwargs)
            try:
                rv = f(*args, **kwargs)
            except Exception as e:
                self.writer.write_val(tag, wname, 'exception:', e.args, e.message)
                +self
                raise
            self.writer.write_val(tag, 'out->' + wname, 'rv-->', rv)
            return rv

        return cdb_rfunc

    # print debugging, unless the first arg is a function
    def __call__(self, *args, **kwargs):
        if args and type(args[0]) == types.FunctionType and len(args) == 1:
            return self.cdb_dec(args[0])
        self.writer.write_val(*args, **kwargs)

    # print value in place
    def __div__(self, other):
        self.writer.write_val(other)
        return other

    # recursively dump a value in place
    def __floordiv__(self, other):
        self.writer.write_dump(self.dumper.dwrap(other))
        return other

    # dump traceback
    def __pos__(self):
        with open('/tmp/cdb', 'a') as f:
            f.write(col_time(time.strftime("%m.%d %H:%M:%S =>")))
            f.write(' - \n')
            lines = traceback.extract_stack()
            lines = lines[:-1]
            for f_name, line, func, stmt in lines:
                #ignore our decorator
                if pstr(func) == 'cdb_rfunc':
                    continue
                f.write(col_stk("\t%s:%s in %s -- " % (repr(f_name), repr(line), repr(func))))
                f.write(repr(stmt))
                f.write('\n')

# cb: the default debug printer
cb = DBPrinter()

glod = ObjectDumper()

glod_long = ObjectDumper()
glod_long.all_members = True
glod_long.f_introspect = 1
glod_long.deep = 4

glod_la = ObjectDumper()
glod_la.all_members = True
glod_la.f_introspect = 7
glod_la.deep = 2

# print object dump
def pod(*x, **y):
    if x:
        for i, v in enumerate(x):
            print col_tag(i)
            print glod.dwrap(v)
    elif y:
        for k, v in y.items():
            print col_tag(k)
            print glod.dwrap(v)

# extended pod
def podx(obj, tag=0, all_members=False, f_intro=0, deep=2, maxd=20):
    """
    podx(obj, tag=0, all_members=False, f_intro=0, deep=2, maxd=20)
    :param obj: object
    :param tag: a label
    :param all_members: boolean (include __ names)
    :param f_intro:  function introspection 1,2,4
    :param deep: int (depth of deep inspections)
    :param maxd: int (depth of recursion)
    :return: nothing
    """
    od = ObjectDumper()
    od.all_members = all_members
    od.f_introspect = f_intro
    od.deep = deep
    print col_tag(tag)
    print od.dwrap(obj)


# long pod
def podl(*x, **y):
    if x:
        for i, v in enumerate(x):
            print col_tag(i)
            print glod_long.dwrap(v)
    elif y:
        for k, v in y.items():
            print col_tag(k)
            print glod_long.dwrap(v)

# other long pod
def podla(*x, **y):
    if x:
        for i, v in enumerate(x):
            print col_tag(i)
            print glod_long.dwrap(v)
    elif y:
        for k, v in y.items():
            print col_tag(k)
            print glod_long.dwrap(v)

# extended dir
def edir(x):
    if type(x) == types.DictionaryType:
        ddir(x)
        return
    if type(x) in IterableTypes:
        idir(x)
        return
    ldir(x)

def ldir(x):
    print "%s:%s" % (col_key(type_str(x)), pstr(x))
    for name in dir(x):
        if name == '__builtins__':
            continue
        obj = getattr(x, name)
        print "  ", col_mem(name), " " * (30 - len(name)), "%s:%s" % (col_key(type_str(obj)), col_none(pstr(obj)))

def ddir(x):
    print "%s" % (col_key(type_str(x)))
    for k,v in x.items():
        if k == '__builtins__' or k == '_':
            continue
        print "  ", col_mem(k), " " * (30 - len(k)), "%s:%s" % (col_key(type_str(v)), col_none(pstr(v)))

def idir(x):
    print "%s" % (col_key(type_str(x)))
    for v in x:
        print "  ", "%s:%s" % (col_key(type_str(v)), col_none(pstr(v)))


#######
# tests
#######
class AAA:
    foo = 1
    bar = 2
    def baz(self): return 7

def test():
    a = [1 ,
         [1,
          set([1,2]),
          frozenset((3,4))
         ],
         (1,2,3)
        ]

    b = AAA()
    b.x = a
    c = {1:2,2:a}
    b.y = c

    b.l = AAA()

    d = {'default_v4': {'ip_version': 4, 'interface': 'Management', 'table': {}, 'defaultrouter': '10.0.144.1'}}


    pod(one=[b])
    pod(two=d)
    edir(a)

if __name__ == '__main__':
    test()
