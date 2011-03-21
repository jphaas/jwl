from corelanguage import TypeStatement, PropertyStatement, PropertyDefinition, KINDS, LiteralStatement, ValidatorStatement, FlagStatement

core_types = []
a = core_types.append

a(TypeStatement('integer',()))
a(TypeStatement('boolean',()))
a(TypeStatement('string',()))
a(TypeStatement('name',('string',)))
a(TypeStatement('guid', ('string',)))
a(TypeStatement('toplevel',('name',)))
a(FlagStatement('toplevel', 'abstract', True))
a(TypeStatement('SafeHTML',('string',)))
a(TypeStatement('url',('string',)))
a(TypeStatement('address',('string',)))
a(TypeStatement('picture',('string',)))
a(TypeStatement('float',()))
a(TypeStatement('date',())) #datetime
a(TypeStatement('timestamp',('float',))) #stored as a floating point
