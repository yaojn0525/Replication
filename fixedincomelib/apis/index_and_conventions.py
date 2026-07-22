import pandas as pd
from typing import Optional, List
# in-house
from fixedincomelib.date import *
from fixedincomelib.market import *


### data conventions 

def qfListAllDataConventions() -> dict:
    return DataConventionRegistry().display_all_data_conventions()

def qfClearDataConventionRegistry(convention : Optional[str]='*') -> None:
    if convention == '*':
        DataConventionRegistry().clear()
    else:
        if DataConventionRegistry().exists(convention):
            DataConventionRegistry().erase(convention)

def qfReloadDataConventionRegistry() -> None:
    DataConventionRegistry().reset_registry()
    DataConventionRegistry()
    print(f'Data convention is reloaded from file.')

def qfRegisterDataConvention(unique_name : str, content : dict) -> None:
    DataConventionRegistry().register(unique_name, content)
    print(f'{unique_name} is registered.')

def qfDisplayDataConvention(data_convention: str) -> pd.DataFrame:
    this_convention : DataConvention = DataConventionRegistry().get(data_convention)
    return this_convention.display()

### index conventions and funding identifiers

def qfListAllIndex() -> dict:
    return IndexRegistry().display_all_indices()

def qfReloadIndexRegistry() -> None:
    IndexRegistry().reset_registry()
    IndexRegistry()
    print(f'All indices are reloaded from file.')

def qfClearIndexRegistry(index : Optional[str]='*') -> None:
    if index == '*':
        IndexRegistry().clear()
    else:
        IndexRegistry().erase(index)

def qfRegisterIndex(index_name : str, index_convention : Dict) -> None:
    IndexRegistry().register(index_name, index_convention)
    print(f'{index_name} is registered.')

def qfDisplayIndex(index_name : str):
    if IndexRegistry().exists(index_name):
        this_index : Index = IndexRegistry().get(index_name)
        return this_index.display()
    
    raise Exception(f"{index_name} does not exist in the index registry!")

def qfListAllFundingIdentifiers() -> dict:
    return FundingIdentifierRegistry().display_all_indices()

def qfReloadFundingIdentifierRegistry() -> None:
    FundingIdentifierRegistry().reset_registry()
    FundingIdentifierRegistry()
    print(f'All funding identifiers are reloaded from file.')

def qfClearFundingIdentifierRegistry(fi : Optional[str]='*') -> None:
    if fi == '*':
        FundingIdentifierRegistry().clear()
    else:
        FundingIdentifierRegistry().erase(fi)

def qfRegisterFundingIdentifier(fi_name : str, content : Dict) -> None:
    FundingIdentifierRegistry().register(fi_name, content)
    print(f'{fi_name} is registered.')

def qfDisplayFundingIdentifier(fi_name : str):
    if FundingIdentifierRegistry().exists(fi_name):
        this_fi : FundingIdentifier = FundingIdentifierRegistry().get(fi_name)
        return this_fi.display()
    
    raise Exception(f"{fi_name} does not exist in the index registry!")

### fixings management

def qfInsertIndexFixing(index : str, dates : str | List, values : float | List) -> None:
    if isinstance(dates, List):
        assert isinstance(values, List) and len(dates) == len(values)
    else:
        dates, values = [dates], [values]
    for each in zip(dates, values):
        d = Date(each[0])
        IndexFixingsManager().insert_fixing(index, d, each[1])
    print(f'{len(dates)} fixing(s) for {index} is(are) inserted.')

def qfRemoveIndexFixings(index : str, dates : Optional[List|str]=None) -> None:

    if index == '*':
        IndexFixingsManager().clear()
        return

    if dates is None:
        IndexFixingsManager().remove_fixing(index)
        print (f'The fixings of {index} are all removed.')
    else:
        these_dates = dates
        if isinstance(these_dates, str):
            these_dates = [dates]
        for date in these_dates:
            IndexFixingsManager().remove_fixing(index, Date(date))
        print(f'{len(these_dates)} fixings of {index} are moved.')

def qfListIndexFixings(
        index : str, 
        start_date : Optional[str]='*', 
        end_date : Optional[str]='') -> pd.DataFrame:
    
    IndexFixingsManager()
    if not IndexFixingsManager().exists(index):
        return pd.DataFrame(columns=['Date', 'Fixing'])
    
    fixings = IndexFixingsManager().get(index)
    if start_date == '*':
        this_df = pd.DataFrame(fixings.items(), columns=['Date', 'Fixing'])
        this_df['Date'] = this_df['Date'].apply(lambda x: x.ISO())
        return this_df
    if end_date == '':
        this_fixing = IndexFixingsManager().get_fixing(index, Date(start_date))
        return pd.DataFrame([[start_date, this_fixing]], columns=['Date', 'Fixing'])
    these_fixings = []
    for k, v in fixings.items():
        if k >= Date(start_date) and k <= Date(end_date):
            these_fixings.append([k.ISO(), v])
    return pd.DataFrame(these_fixings, columns=['Date', 'Fixing'])

def qfListAllIndexFixings(index : Optional[str]='*') -> pd.DataFrame:
    if index == '*':
        return pd.DataFrame(IndexFixingsManager().get_keys, columns=['Index'])
    else: 
        if not IndexFixingsManager().exists(index):
            return pd.DataFrame(columns=['Date', 'Fixing'])
        fixings = IndexFixingsManager().get(index)
        return pd.DataFrame(fixings.items(), columns=['Date', 'Fixing'])

def qfReloadIndexFixings() -> None:
    IndexFixingsManager().reset_registry()
    IndexFixingsManager()
    print(f'All fxings are reloaded from file.')

        


