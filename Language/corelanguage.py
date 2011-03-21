"""Contains classes for constructing syntax trees for the data definition language and the query language"""from ast import Node#data definition languageclass TypeStatement(Node):    parameters = ['name','parents']    class PropertyStatement(Node):    parameters = ['a', 'b']class PropertyDefinition(Node):    parameters = ['typename','kind','name']    class FlagStatement(Node): #allows you to attach meta-data that does NOT inherit to a type.  For inheritance, use LiteralStatement instead    parameters = ['typename','name','value']    class KINDS:    NONE = 0    SINGLE = 1    PLURAL = 2    REFLECT = 3class LiteralStatement(Node):    parameters = ['typename', 'name', 'literal']class ValidatorStatement(Node):    parameters = ['typename', 'validator']    #convenience methodsNONE = KINDS.NONESINGLE = KINDS.SINGLEPLURAL = KINDS.PLURALREFLECT = KINDS.REFLECTdef newtype(lang):    def nt(name, *parents):        lang.append(TypeStatement(name,parents))    return nt    def setprop(lang):    def sp(typea, kinda, propa, typeb, kindb = KINDS.NONE, propb = ''):        lang.append(PropertyStatement(PropertyDefinition(typea, kinda, propa), PropertyDefinition(typeb, kindb, propb)))    return sp    def setliteral(lang):    return lambda(typename, name, literal): lang.append(LiteralStatement(typename, name, literal))def setvalidator(lang):    return lambda (typename, validator): lang.append(ValidatorStatement(typename, validator))    def setflag(lang):    return lambda typename, name, value: lang.append(FlagStatement(typename, name, value))    #query languageclass QueryNode(Node):    passclass SetTransform(QueryNode):    pass    class SetBool(QueryNode):    pass    class Set(QueryNode):    pass    class GetV(SetTransform):    parameters = ['type', 'property']    class ValueSet(Set):    parameters = ['values']    class TypeSet(Set):    parameters = ['type']    class Filter(SetTransform):    parameters = ['filters']    class LimitFilter(SetBool):    parameters = ['number', 'offset']    class Compare(SetBool):    parameters = ['value']    class GT(Compare):    pass    class LT(Compare):    pass    class GTE(Compare):    pass    class LTE(Compare):    pass    class EQ(Compare):    passclass NE(Compare):    passclass Command(Node):    pass  class GetSet(Command):    parameters = ['values']class List(Command):  #List(typename, value) means that TypeSet(typename) will include value    parameters = ['values', 'type']    class Unlist(Command):  #Unlist(typename, value) is the inverse of List -- TypeSet(typename) will not include value    parameters = ['values', 'type']    class Add(Command):    parameters = ['values', 'type', 'property', 'value']class Remove(Command):    parameters = ['values', 'type', 'property', 'value']class RemoveAll(Command):    parameters = ['values', 'type', 'property']    class Replace(Command):    parameters = ['values', 'type', 'property', 'newvalues']        #Data Language: This is a formal method of passing raw cache data from one data-store to another (particularly from cache to cache)#Two basic commands: exists(value, type, property, target) -- means that target is the result of a GetV on value for the given type and property#not_exists(value, type, property) -- means that all data for this GetV should be completely deleted#Then is_listed(value, type, true) -- means that this value should be listed for this type; is_listed(value, type, false) means that it should be unlistedclass exists(Node):    parameters = ['value', 'type', 'property', 'target']class not_exists(Node):    parameters = ['value', 'type', 'property']    class is_listed(Node):    parameters = ['value', 'type', 'listed']