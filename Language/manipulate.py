def serialize_query(query):
    """given a query, executes it and returns a list of dicts, or a single dict, representing the results of the query"""
    if query._single:
        return serialize_query_single(query)
    else:
        return [serialize_query_single(q) for q in query.eval]
    
def serialize_query_single(query):
    """given a query representing a single object, serializes it to a dict"""
    return dict((propname, query[propname].value) for propname in query.meta)