from nsepython import nse_optionchain_scrapper
import pandas as pd

def get_options():
    data = nse_optionchain_scrapper("NIFTY")

    ce, pe = [], []

    for i in data['records']['data']:
        if i.get("CE"):
            ce.append(i["CE"])
        if i.get("PE"):
            pe.append(i["PE"])

    return pd.DataFrame(ce), pd.DataFrame(pe)
