from Utils.multimethods import getNamespace
mm = getNamespace()
from Language.ast import Node
from Language.corelanguage import Set, ValueSet, Filter, GetV, QueryNode, SetBool, KINDS, PropertyStatement, GetSet, Add, Remove, RemoveAll #,Delete
from Language.bake import generate_metas

class Reference(QueryNode):
    """A reference represents a property-reference in a query.  It consists of the origin set and the type/property of the reference"""
    parameters = ['origin_set', 'type', 'property']
    
class Comparison(QueryNode):
    """Represents a comparison in a filter.  Consists of the origin set and the comparison object"""
    parameters = ['origin_set', 'compare']
    
@mm(tuple)
def parse(query):
    """Returns (reference, (comparison, comparison))"""
    return checkdone(None, (), query)
    
def checkdone(current_reference, filters, continuation):
    if continuation == ():
        return (current_reference, filters)
    return parse(continuation[0], current_reference, filters, continuation[1:])
    
@mm(Set, object, tuple, tuple)
def parse(node, current_reference, filters, continuation):
    if current_reference is not None:
        raise Exception("Query parsing error: sets cannot be preceded by any other operator")
    return checkdone(node, filters, continuation)
    
@mm(GetV, object, tuple, tuple)
def parse(node, current_reference, filters, continuation):
    if current_reference is None:
        raise Exception("Query parsing error: GetV must be preceded by another operator")
    return checkdone(Reference(current_reference, node.type, node.property), filters, continuation)

@mm(Filter, object, tuple, tuple)
def parse(node, current_reference, filters, continuation):
    newfilters = reduce(lambda x, y: x + y, (checkdone(current_reference, (), f)[1] for f in node.filters))
    return checkdone(current_reference, filters + newfilters, continuation)
    
@mm(SetBool, object, tuple, tuple)
def parse(node, current_reference, filters, continuation):
    if current_reference is None:
        raise Exception("Query parsing error: SetBools must be preceded by another operator")
    if continuation != ():
        raise Exception("Query parsing error: SetBools cannot be preceded by any further operators")
    return (None, filters + (Comparison(current_reference, node),))
    
    
def buildTables(metas):
    """
    Translates a language into a set of relational tables.  {tablename: []}
    """
    tables = {}
    for m in metas:
        for prop in m.values():
            if isinstance(prop, PropertyStatement):
                tablename, objectcolumn, valuecolumn = getColumnP(prop)
                if not tables.has_key(tablename):
                    tables[tablename] = []
                if not objectcolumn in tables[tablename]:
                    tables[tablename].append(objectcolumn)
                if not valuecolumn in tables[tablename]:
                    tables[tablename].append(valuecolumn)
    return tables

def getColumnP(prop):
    """
    (property): (tablename, objectcolumn, valuecolumn)
    Translates the type/property into the underlying table, value-column, and object-column.
    """
    if prop.a.kind == KINDS.SINGLE: #one-to-one or one-to-many: look up on own table
        return (singletable(typename), selfname(), columnname(prop.a.name))
    elif prop.b.kind == KINDS.SINGLE: #many-to-one: look up on other type's table
        return (singletable(prop.b.typename), columnname(prop.b.name), selfname())
    else: #many-to-many: look up on join table
        return (jointable(typename, prop.b.typename), joincolumn(typename), joincolumn(prop.b.typename))
    
def getColumn(typename, property, metas):
    """
    (typename, propertyname): (tablename, objectcolumn, valuecolumn)
    Translates the type/property into the underlying table, value-column, and object-column.
    """
    prop = metas[typename][property]
    if not isinstance(prop, PropertyStatement):
        raise Exception('type ' + type + ' property ' + property + ' not a valid proeprty')
    return getColumnP(prop)
    
def jointable(typea, typeb):
    """returns the name of the join table (ie, decides which type comes first)"""
    return 'j_' + typea + '_' + typeb if typea > typeb else 'j_' + typeb + '_' + typea

def singletable(typename):
    """returns the name of the single table"""
    return 's_' + typename

def columnname(property):
    return 'p_' + property

def joincolumn(typename):
    return 't_' + typename

def selfname():
    return 'self'
    
class RelationalSchema(object):
    """Represents the schema for a relational database, given a language"""
    def __init__(self, language):
        self._metas = generate_metas(language)
        self.tables = buildTables(language, self._metas)
        
    def getColumn(self, typename, property):
        return getColumn(tpename, property, self._metas)
        
        
        
def build_sql_query(query, sqlfunction):
    return _build(query, sqlfunction)
    
@mm(GetSet, RelationalSchema, object)
def _build(command, rschema, sqlfunction):
    reference, filters = parse(command.values)
    
    
#@mm(Delete, object)
#def _build(command, sqlfunction):
#    pass
    
@mm(Add, object)
def _build(command, sqlfunction):
    pass
    
@mm(Remove, object)
def _build(command, sqlfunction):
    pass
    
@mm(RemoveAll, object)
def _build(command, sqlfunction):
    pass

def _toSql(reference, filters):
    pass

class InnerJoin(Node):
    parameters = ['name', 'alias', 'joincolumn', 'jointable', ]

def appendJoins():
    pass

##SOMETHING TO BE CAREFUL ABOUT: IF YOU FILTER ON A SET THAT HAS MORE THAN ONE VALUE, YOU COULD END
##UP WITH REPEATS IF YOU MESS UP