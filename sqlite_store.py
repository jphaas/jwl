import sqlite3

def guess_type(obj):
    types = {int: 'integer', long: 'integer', float: 'real', str: 'text', unicode: 'text'}
    for k, v in types.iteritems():
        if isinstance(obj, k): return v
    return 'text'

class Store:
    def __init__(self, conn):
        self.conn = conn
        conn.row_factory = sqlite3.Row
        cols = [r['name'] for r in conn.execute('pragma table_info(' + self.table + ')')]
        self.cols = cols
        if len(cols) == 0:
            conn.execute('create table ' + self.table + '()')
        
    def insert(self, row):
        for k, v in row.iteritems():
            if k not in self.cols:
                self.conn.execute('alter table add column ' + k + ' ' + guess_type(v))
                self.cols.append(k)
        self.conn.execute('insert into ' + self.table + '(%s) VALUES (%s)'%(', '.join(row.keys()), ', '.join(row.values())))

        
    table = 'data'