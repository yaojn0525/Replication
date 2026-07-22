import pickle
from typing import List
# in-house
from fixedincomelib.model import *


def qfCreateBuildMethod(build_method_type : str, content : dict):
    assert 'TARGET' in content
    func = BuildMethodBuilderRegistry().get(build_method_type)
    return func(content['TARGET'], content)

def qfWriteBuildMethodToFile(build_method : BuildMethod, path : str):
    this_dict = build_method.serialize()
    with open(path, 'wb') as handle:
        pickle.dump(this_dict, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return 'DONE'

def qfReadBuildMethodFromFile(path : str):
    with open(path, 'rb') as handle:
        this_dict = pickle.load(handle)
        this_type = this_dict['TYPE']
        this_key = f'{this_type}_DES'
        func = BuildMethodBuilderRegistry().get(this_key)
        return func(this_dict)
         
def qfCreateModelBuildMethodCollection(bm_list : List[BuildMethod]):
    return BuildMethodCollection(bm_list)

def qfGetBuildMethodFromBuildMethodCollection(
        build_method_collection : BuildMethodCollection, 
        target : str, 
        build_method_type : str):

    return build_method_collection.get_build_method_from_build_method_collection(target, build_method_type)

def qfWriteBuildMethodCollectionToFile(bmc : BuildMethodCollection, path : str):
    this_dict = bmc.serialize()
    with open(path, 'wb') as handle:
        pickle.dump(this_dict, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return 'DONE'

def qfReadBuildMethodCollectionFromFile(path : str):
    with open(path, 'rb') as handle:
        this_dict = pickle.load(handle)
        return BuildMethodCollection.deserialize(this_dict)
    
def qfDisplayModelBuildMethod(bm : BuildMethod):
    return bm.display()

def qfDisplayModelBuildMethodCollection(bmc : BuildMethodCollection):
    return bmc.display()