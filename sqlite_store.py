import sqlite3

types = {int: 'integer', long: 'integer', float: 'real', str: 'text', unicode: 'text'}
def guess_type(obj):
    for k, v in types.iteritems():
        if isinstance(obj, k): return v
    return 'text'
def clean_v(obj):
    for k, v in types.iteritems():
        if isinstance(obj, k): return obj
    return str(obj)

class Store:
    def __init__(self, conn):
        self.conn = conn
        conn.row_factory = sqlite3.Row
        cols = [r['name'] for r in conn.execute('pragma table_info(' + self.table + ')')]
        self.cols = cols
        if len(cols) == 0:
            conn.execute('create table ' + self.table + '(rid INTEGER PRIMARY KEY)')
        
    def insert(self, row):
        for k, v in row.iteritems():
            if k not in self.cols:
                self.conn.execute('alter table ' + self.table + ' add column "' + k + '" ' + guess_type(v))
                self.cols.append(k)
        self.conn.execute('insert into ' + self.table + '(%s) VALUES (%s)'%(', '.join(['"' + k + '"' for k in row.keys()]), ', '.join(['?' for v in row.values()])),
                [clean_v(v) for v in row.values()])

    
        
    table = 'data'
