import sqlite3
from OrderedDict import OrderedDict

types = {int: 'integer', long: 'integer', float: 'real', str: 'text', unicode: 'text'}
def guess_type(obj):
    for k, v in types.iteritems():
        if isinstance(obj, k): return v
    return 'text'
def clean_v(obj):
    for k, v in types.iteritems():
        if isinstance(obj, k): return obj
    return str(obj)

def safe_execute(func):
    def new_func(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except sqlite3.OperationalError, e:
            return [{'msg': 'error loading metrics: ' + str(e)}]
    return new_func

class Store:
    table = 'data'
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

    
class ObjectQuery:
    def __init__(self, conn):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self.tz = 0
    @safe_execute
    def get(self, table, columns, list_column = None, filter=''):
        q = 'select ' + ', '.join(columns) + ' from ' + table + ' ' + filter
        try:
            raw = self.conn.execute(q)
        except:
            raise
        columnsClean = [c.split()[-1] for c in columns]
        def process_row(r):
            obj = OrderedDict(zip(columnsClean, r))
            if list_column is not None:
                obj['expand_list'] = list_column(obj)
            return obj
        return [process_row(r) for r in raw]
    @safe_execute
    def get_raw(self, query):
        raw = list(self.conn.execute(query))
        columns = raw[0].keys() if len(raw) > 0 else []
        columns = [c.replace('"', '') for c in columns] #sqlite weirdly returns the quotes around columns sometimes?
        return [OrderedDict(zip(columns, r)) for r in raw] 
    @safe_execute
    def get_grouped(self, table, groups, filter):
        columns_flat = (col for group in groups for col in group)
        q = 'select ' + ', '.join(columns_flat) + ' from ' + table + ' ' + filter
        try:
            raw = self.conn.execute(q)
        except:
            raise
        def process(groups, rows):
            columnsClean = [c.split()[-1] for c in groups[0]]
            if len(groups) == 1:
                return [OrderedDict((col, r[col]) for col in columnsClean) for r in rows] 
            g_col = columnsClean[0]
            output = []
            cur = None
            cur_rows = []
            def add_to_output():
                if len(cur_rows) > 0:
                    obj = OrderedDict((col, cur_rows[0][col]) for col in columnsClean)
                    obj['expand_list'] = process(groups[1:], cur_rows)
                    output.append(obj)
            for r in rows:
                if cur is None or r[g_col] != cur:
                    add_to_output()
                    cur_rows = [] 
                    cur = r[g_col]
                cur_rows.append(r)
            add_to_output()
            return output
        r = process(groups, raw)
        return r
        