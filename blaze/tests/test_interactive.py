from blaze.interactive import (Data, compute, concrete_head, expr_repr,
        to_html)
import os

from into import into, append
from into.backends.csv import CSV
from blaze.compute.core import compute
from blaze.compute.python import compute
from blaze.expr import symbol
from datashape import dshape
from blaze.utils import tmpfile, example
import pytest
import sys

import pandas as pd
import numpy as np

data = (('Alice', 100),
        ('Bob', 200))

L = [[1, 'Alice',   100],
     [2, 'Bob',    -200],
     [3, 'Charlie', 300],
     [4, 'Denis',   400],
     [5, 'Edith',  -500]]

t = Data(data, columns=['name', 'amount'])

x = np.ones((2, 2))

def test_table_raises_on_inconsistent_inputs():
    with pytest.raises(ValueError):
        t = Data(data, schema='{name: string, amount: float32}',
            dshape=dshape("{name: string, amount: float32}"))


def test_resources():
    assert t._resources() == {t: t.data}


def test_resources_fail():
    t = symbol('t', 'var * {x: int, y: int}')
    d = t[t['x'] > 100]
    with pytest.raises(ValueError):
        compute(d)


def test_compute_on_Data_gives_back_data():
    assert compute(Data([1, 2, 3])) == [1, 2, 3]


def test_len():
    assert len(t) == 2
    assert len(t.name) == 2


def test_compute():
    assert list(compute(t['amount'] + 1)) == [101, 201]


def test_create_with_schema():
    t = Data(data, schema='{name: string, amount: float32}')
    assert t.schema == dshape('{name: string, amount: float32}')


def test_create_with_raw_data():
    t = Data(data, columns=['name', 'amount'])
    assert t.schema == dshape('{name: string, amount: int64}')
    assert t.name
    assert t.data == data


def test_repr():
    result = expr_repr(t['name'])
    print(result)
    assert isinstance(result, str)
    assert 'Alice' in result
    assert 'Bob' in result
    assert '...' not in result

    result = expr_repr(t['amount'] + 1)
    print(result)
    assert '101' in result

    t2 = Data(tuple((i, i**2) for i in range(100)), fields=['x', 'y'])
    assert t2.dshape == dshape('100 * {x: int64, y: int64}')

    result = expr_repr(t2)
    print(result)
    assert len(result.split('\n')) < 20
    assert '...' in result


def test_repr_of_scalar():
    assert repr(t.amount.sum()) == '300'


def test_mutable_backed_repr():
    mutable_backed_table = Data([[0]], fields=['col1'])
    repr(mutable_backed_table)


def test_dataframe_backed_repr():
    df = pd.DataFrame(data=[0], columns=['col1'])
    dataframe_backed_table = Data(df)
    repr(dataframe_backed_table)


def test_dataframe_backed_repr_complex():
    df = pd.DataFrame([(1, 'Alice', 100),
                       (2, 'Bob', -200),
                       (3, 'Charlie', 300),
                       (4, 'Denis', 400),
                       (5, 'Edith', -500)],
                      columns=['id', 'name', 'balance'])
    t = Data(df)
    repr(t[t['balance'] < 0])


def test_expr_repr_empty():
    s = repr(t[t.amount > 1e9])
    assert isinstance(s, str)
    assert 'amount' in s


def test_to_html():
    s = to_html(t)
    assert s
    assert 'Alice' in s
    assert '<table' in s

    assert to_html(1) == '1'

    assert to_html(t.count()) == '2'

def test_to_html_on_arrays():
    s = to_html(Data(np.ones((2, 2))))
    assert '1' in s
    assert 'br>' in s


def test_repr_html():
    assert '<table' in t._repr_html_()


def test_into():
    assert into(list, t) == into(list, data)


def test_serialization():
    import pickle
    t2 = pickle.loads(pickle.dumps(t))

    assert t.schema == t2.schema
    assert t._name == t2._name


def test_table_resource():
    with tmpfile('csv') as filename:
        ds = dshape('var * {a: int, b: int}')
        csv = CSV(filename)
        append(csv, [[1, 2], [10, 20]], dshape=ds)

        t = Data(filename)
        assert isinstance(t.data, CSV)
        assert into(list, compute(t)) == into(list, csv)


def test_concretehead_failure():
    t = symbol('t', 'var * {x:int, y:int}')
    d = t[t['x'] > 100]
    with pytest.raises(ValueError):
        concrete_head(d)


def test_into_np_ndarray_column():
    t = Data(L, fields=['id', 'name', 'balance'])
    expr = t[t.balance < 0].name
    colarray = into(np.ndarray, expr)
    assert len(list(compute(expr))) == len(colarray)


def test_into_nd_array_selection():
    t = Data(L, fields=['id', 'name', 'balance'])
    expr = t[t['balance'] < 0]
    selarray = into(np.ndarray, expr)
    assert len(list(compute(expr))) == len(selarray)


def test_into_nd_array_column_failure():
    tble = Data(L, fields=['id', 'name', 'balance'])
    expr = tble[tble['balance'] < 0]
    colarray = into(np.ndarray, expr)
    assert len(list(compute(expr))) == len(colarray)


def test_Data_attribute_repr():
    t = Data(CSV(example('accounts-datetimes.csv')))
    result = t.when.day
    expected = pd.DataFrame({'when_day': [1,2,3,4,5]})
    assert repr(result) == repr(expected)


def test_can_trivially_create_csv_Data():
    Data(example('iris.csv'))


def test_can_trivially_create_csv_Data_with_unicode():
    if sys.version[0] == '2':
        assert isinstance(Data(example(u'iris.csv')).data, CSV)


def test_can_trivially_create_sqlite_table():
    pytest.importorskip('sqlalchemy')
    Data('sqlite:///'+example('iris.db')+'::iris')


def test_can_trivially_create_pytables():
    pytest.importorskip('tables')
    Data(example('accounts.h5')+'::/accounts')


def test_data_passes_kwargs_to_resource():
    assert Data(example('iris.csv'), encoding='ascii').data.encoding == 'ascii'


def test_data_on_iterator_refies_data():
    data = [1, 2, 3]
    d = Data(iter(data))

    assert into(list, d) == data
    assert into(list, d) == data


def test_Data_on_json_is_concrete():
    d = Data(example('accounts-streaming.json'))

    assert compute(d.amount.sum()) == 100 - 200 + 300 + 400 - 500
    assert compute(d.amount.sum()) == 100 - 200 + 300 + 400 - 500


def test_repr_on_nd_array_doesnt_err():
    d = Data(np.ones((2, 2, 2)))
    repr(d + 1)


def test_generator_reprs_concretely():
    x = [1, 2, 3, 4, 5, 6]
    d = Data(x)
    expr = d[d > 2] + 1
    assert '4' in repr(expr)
