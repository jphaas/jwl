import inspect

def decorate(original, replacement):
    """
    For defining decorators that don't destroy function metadata.
    
    Original and replacement must have compatible signatures.
    
    Usage: 
    def my_decorator(original):
        def replacement():
            ...
        return decorate(original, replacement)
    """
    scope = dict(f = replacement)
    exec 'def ' + original.__name__ + inspect.formatargspec(*inspect.getargspec(original)) + ': return f' + inspect.formatargspec(*inspect.getargspec(original)[:3]) in scope
    f2 = scope[original.__name__]
    for key in dir(original):
        if not hasattr(f2, key):
            setattr(f2, key, getattr(original, key))
    return f2