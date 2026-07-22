import pickle
import pandas as pd
from typing import List
# in-house
from fixedincomelib.data import *
from fixedincomelib.market import *


def qfCreateData1D(data_type : str, data_conv : str, df : pd.DataFrame):
    axis1 = df.index.tolist()
    values = df['values'].tolist()
    data_conv_obj = DataConventionRegistry().get(data_conv)
    return Data1D(data_type, data_conv_obj, axis1, values)

def qfCreateData2D(data_type : str, data_conv : str, df : pd.DataFrame):
    axis1 = df.index.tolist()
    axis2 = df.columns.tolist()
    values = df.values.tolist()
    data_conv_obj = DataConventionRegistry().get(data_conv)
    return Data2D(data_type, data_conv_obj, axis1, axis2, values)

def qfCreateDataTable(data_type : str, data_conv : str, df : pd.DataFrame):
    columns = df.columns.tolist()
    values = df.values.tolist()
    data_conv_obj = DataConventionRegistry().get(data_conv)
    return DataTable(data_type, data_conv_obj, columns, values)

def qfCreateDataGeneric(data_label : str, df : pd.DataFrame):
    columns = df.columns.tolist()
    values = df.values.tolist()    
    return DataGeneric(data_label, columns, values)

def qfDisplayDataObject(data : DataObject):
    return data.display()

def qfWriteDataObjectToFile(data : DataObject, path : str):
    this_dict = data.serialize()
    with open(path, 'wb') as handle:
        pickle.dump(this_dict, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return 'DONE'

def qfReadDataObjectFromFile(path : str):
    with open(path, 'rb') as handle:
        this_dict = pickle.load(handle)
        assert 'DATA_SHAPE' in this_dict
        func = DataObjectDeserializerRegistry().get(this_dict['DATA_SHAPE'])
        return func(this_dict)

def qfCreateDataCollection(data_objects : List[DataObject]):
    return DataCollection(data_objects)

def qfGetDataFromDataCollection(
        data_collection : DataCollection, 
        data_type : str, 
        data_conv : str):
    return data_collection.get_data_from_data_collection(data_type, data_conv)

def qfDisplayDataCollection(data_collection : DataCollection):
    return data_collection.display()

def qfWriteDataCollectionToFile(data_collection : DataCollection, path : str):
    this_dict = data_collection.serialize()
    with open(path, 'wb') as handle:
        pickle.dump(this_dict, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return 'DONE'

def qfReadDataCollectionFromFile(path : str):
    with open(path, 'rb') as handle:
        this_dict = pickle.load(handle)
        return DataCollection.deserialize(this_dict)

