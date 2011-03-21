"""
Supports multi-methods, modified from http://www.artima.com/weblogs/viewpost.jsp?thread=101605.

Big change: supports inheritance.  When there are multiple matching functions,
1. An exact match wins
...
2. An exact match on the first, second items win
3. An exact match on the first item wins
4. Order of declaration wins (ugly if functions are defined in multiple modules!)
"""

from UserDict import DictMixin

class OrderedDict(dict, DictMixin):

    def __init__(self, *args, **kwds):
        if len(args) > 1:
            raise TypeError('expected at most 1 arguments, got %d' % len(args))
        try:
            self.__end
        except AttributeError:
            self.clear()
        self.update(*args, **kwds)

    def clear(self):
        self.__end = end = []
        end += [None, end, end]         # sentinel node for doubly linked list
        self.__map = {}                 # key --> [key, prev, next]
        dict.clear(self)

    def __setitem__(self, key, value):
        if key not in self:
            end = self.__end
            curr = end[1]
            curr[2] = end[1] = self.__map[key] = [key, curr, end]
        dict.__setitem__(self, key, value)

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        key, prev, next = self.__map.pop(key)
        prev[2] = next
        next[1] = prev

    def __iter__(self):
        end = self.__end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self):
        end = self.__end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def popitem(self, last=True):
        if not self:
            raise KeyError('dictionary is empty')
        if last:
            key = reversed(self).next()
        else:
            key = iter(self).next()
        value = self.pop(key)
        return key, value

    def __reduce__(self):
        items = [[k, self[k]] for k in self]
        tmp = self.__map, self.__end
        del self.__map, self.__end
        inst_dict = vars(self).copy()
        self.__map, self.__end = tmp
        if inst_dict:
            return (self.__class__, (items,), inst_dict)
        return self.__class__, (items,)

    def keys(self):
        return list(self)

    setdefault = DictMixin.setdefault
    update = DictMixin.update
    pop = DictMixin.pop
    values = DictMixin.values
    items = DictMixin.items
    iterkeys = DictMixin.iterkeys
    itervalues = DictMixin.itervalues
    iteritems = DictMixin.iteritems

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, self.items())

    def copy(self):
        return self.__class__(self)

    @classmethod
    def fromkeys(cls, iterable, value=None):
        d = cls()
        for key in iterable:
            d[key] = value
        return d

    def __eq__(self, other):
        if isinstance(other, OrderedDict):
            return len(self)==len(other) and self.items() == other.items()
        return dict.__eq__(self, other)

    def __ne__(self, other):
        return not self == other

class MultiMethod(object):
    def __init__(self, name):
        self.name = name
        self.typemap = OrderedDict()
    def _find(self, types):
        best = -1
        winner = None
        #print 'in lookup: ', types
        #print 'typemap: '
        #for t in self.typemap:
        #    print t
        for sig in self.typemap:
            if len(types) == len(sig):
                score = 0
                while types[:score + 1] == sig[:score + 1] and score + 1 <= len(types):
                    score += 1
                for t, s in zip(types, sig)[score:]:
                    score = score if issubclass(t, s) else -1
                if score > best:
                    best = score
                    winner = sig
        if winner is None:
            raise TypeError("no match for method " + self.name + " with args of type " + repr(types))
        return self.typemap[winner]
        
    def __call__(self, *args):
        types = tuple(arg.__class__ for arg in args) # a generator expression!
        function = self._find(types)          
        return function(*args)
    def register(self, types, function):
        if types in self.typemap:
            raise TypeError("duplicate registration")
        self.typemap[types] = function

def getNamespace():
    registry = {}
    def mm(*types):
        def register(function):
            name = function.__name__
            mm = registry.get(name)
            if mm is None:
                mm = registry[name] = MultiMethod(name)
            mm.register(types, function)
            def fun(*args):
                return mm(*args)
            return fun
        return register
    return mm