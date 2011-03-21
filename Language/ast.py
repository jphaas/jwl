"""
Utility functions for creating abstract-syntax-tree-like object hierarchies
"""

def _compare(n1, n2):
    if type(n1) is tuple:
        return _compare(list(n1), n2)
    if type(n2) is tuple:
        return _compare(n1, list(n2))
    if type(n1) != type(n2):
        return False
    if isinstance(n1, Node) and isinstance(n2, Node):
        if len(n1._raw) != len(n2._raw):
            return False
        for n1a, n2a in zip(n1._raw, n2._raw):
            if not _compare(n1a, n2a):
                return False
        return True
    else:
        return n1 == n2

class Node(object):
    parameters = []
    def __init__(self, *args):
        if len(args) != len(self.parameters):
            raise Exception('expected ' + repr(len(self.parameters)) + ' arguments but got ' + repr(len(args)))
        for p, a in zip(self.parameters, args):
            setattr(self, p, a)
        self._raw = args
    def __eq__(self, other):
        return _compare(self, other)
    def __ne__(self, other):
        return not _compare(self, other)
    def __repr__(self):
        return '%s(%s)'%(type(self).__name__, ', '.join(repr(a) for a in self._raw))

