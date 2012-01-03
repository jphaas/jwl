import tornado.database
import _mysql_exceptions
from OrderedDict import OrderedDict
import datetime

types = {int: 'integer', long: 'integer', float: 'real', str: 'varchar(1000)', unicode: 'varchar(1000)'}
def guess_type(obj):
    for k, v in types.iteritems():
        if isinstance(obj, k): return v
    return 'varchar(1000)'
def clean_v(obj):
    for k, v in types.iteritems():
        if isinstance(obj, k): return obj
    return unicode(obj)

def safe_execute(func):
    def new_func(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except _mysql_exceptions.ProgrammingError, e:
            return [{'msg': 'error loading metrics: ' + unicode(e)}]
    return new_func

class Store:
    table = 'data'
    def __init__(self, conn):
        self.conn = conn
        try:
            cols = [r['Field'].lower() for r in conn.query('show columns from ' + self.table)]
            self.cols = cols
        except:
            self.cols = []
            conn.execute('create table ' + self.table + '(rid INT PRIMARY KEY AUTO_INCREMENT)')
        
    def insert(self, row):
        for k, v in row.iteritems():
            if k.lower() not in self.cols:
                self.conn.execute('alter table ' + self.table + ' add column `' + k + '` ' + guess_type(v))
                self.cols.append(k)
        self.conn.execute('insert into ' + self.table + '(%s) VALUES (%s)'%(', '.join(['`' + k + '`' for k in row.keys()]), ', '.join(['%s' for v in row.values()])), *[clean_v(v) for v in row.values()])

def _filter(rows):
    for row in rows:
        for key, value in row.iteritems():
            if isinstance(value, datetime.timedelta):
                raise Exception(key)
    return rows
    
class ObjectQuery:
    def __init__(self, conn):
        self.conn = conn
        self.tz = 0
        
    @safe_execute
    def get(self, table, columns, list_column = None, filter=''):
        q = 'select ' + ', '.join(columns) + ' from ' + table + ' ' + filter
        try:
            raw = self.conn.query(q)
        except:
            raise
        columnsClean = [c.split()[-1] for c in columns]
        def process_row(r):
            obj = OrderedDict(zip(columnsClean, r))
            if list_column is not None:
                obj['expand_list'] = list_column(obj)
            return obj
        return _filter([process_row(r) for r in raw])
    @safe_execute
    def get_raw(self, query):
        raw = self.conn.query(query)
        return raw
    @safe_execute
    def get_grouped(self, table, groups, filter):
        columns_flat = (col for group in groups for col in group)
        q = 'select ' + ', '.join(columns_flat) + ' from ' + table + ' ' + filter
        try:
            raw = self.conn.query(q)
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
        