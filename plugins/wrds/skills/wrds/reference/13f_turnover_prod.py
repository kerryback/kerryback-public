import datetime

currentDT_start = datetime.datetime.now()
print (str(currentDT_start))

#####################################################
# Calculate Trades, Flows and Turnover Ratios       #
# Python code: Qingyi (Freda) Song Drechsler        #
# Edits: Alex Malek                                 #
# Original SAS code:                                #
# Luis Palacios, Rabih Moussawi, and Denys Glushkov #
# November 2018                                     #
# August 2021                                       #
# Input  - Thomson-Reuters 13F Data (TR-13F)        #
#          S34TYPE3 Holdings data                   #
#          S34TYPE1 data                            #
#          CRSP Stock File data                     #
# Output - TRADES data with detailed Buys & Sales   #
#          by each institution                      #
#          AGGREGATES data with Total Buys & Sales  #
#          Assets, Flows and Turnover Measures      #
#####################################################

import pandas as pd
import numpy as np
import wrds
import datetime as dt
###################
# Connect to WRDS #
###################
conn=wrds.Connection()

def reduce_mem_usage(df, verbose=1):
    """ 
    Downcast int/float types if possible to reduce memory usage.    
    Convert object to category, very efficient if objects have less then 50% unique values
    """
    start_mem = df.memory_usage().sum() / 1024**2
    if verbose > 0:
        print(('Memory usage of dataframe is {:.2f} MB').format(start_mem))
    for col in df.columns:
        col_type = df[col].dtype        
        t_str = str(col_type)
        t_str_new = t_str
        if ('int' in t_str or 'float' in t_str):
            is_int = ('int' in t_str)
            # test if float can be converted to int
            # Note NA values cannot be cast to Int
            if 'float' in t_str:
                is_int = (df[col] % 1  == 0).all()
            if is_int:
                if df[col].min() >= 0:
                    df[col] = pd.to_numeric(df[col], downcast='unsigned')
                else:
                    df[col] = pd.to_numeric(df[col], downcast='integer')
            else:
                df[col] = pd.to_numeric(df[col], downcast='float')
        if (t_str == 'object'):
            df[col] = df[col].astype('category')
        t_str_new=df[col].dtype
        if verbose > 1:
            if verbose > 2 or t_str!=t_str_new:
                print(f"\t{col}:\t{t_str} -> {t_str_new}")
            if verbose > 2 and t_str!=t_str_new:
                mem = df.memory_usage().sum() / 1024**2
                print(("\tmem usage after type chg: {:.2f} MB").format(mem))
    end_mem = df.memory_usage().sum() / 1024**2
    if verbose > 0:
        print(('Memory usage after optimization is: {:.2f} MB').format(end_mem))
        print('Decreased by {:.1f}%'.format(100 * (start_mem - end_mem) / start_mem))
    
    return df

######################################
# Step 1                             #
# CRSP Block                         #
######################################

# set sample date range
begdate = '03/01/1980'
enddate = '12/31/2010'

# sql to extract data from CRSP

price = conn.raw_sql(f"""
                      select permno::INT, date, cfacpr, cfacshr, shrout, prc, ret
                      from crsp.msf 
                      where date between '{begdate}' and '{enddate}'
                      """, date_cols=['date'])

# get month and quarter-end dates
price['mdate']=price['date']+pd.offsets.MonthEnd(0)
price['qdate']=price['date']+pd.offsets.QuarterEnd(0)

# calculate adjusted price, total shares and market cap
price['p']=price['prc'].abs()/price['cfacpr'] # price adjusted
price['tso']=price['shrout']*price['cfacshr']*1e3 # total shares out adjusted

# Keep only the records with shrout>0
price = price[price['shrout']>0]

# keep only relevant columns
price = price[['permno','mdate','qdate','date','cfacshr', 'p', 'tso','ret']]

# create log return for computing quarterly compounded return
price['ret'] = price['ret'].fillna(0)
price['logret'] = np.log(1+price['ret'])

qret = price.groupby(['permno','qdate'])['logret'].sum().reset_index()
qret['qret']=np.exp(qret['logret'])-1

# shift qdate by one quarter to make qret next quarter return
qret['qdate']=qret['qdate']+pd.offsets.QuarterEnd(-1)
qret = qret.drop(columns=['logret'], axis=1)

# Finalize CRSP Subset - Keep Quarterly Observations 
# And Add Forward Quartely Returns
price = price[price['qdate']==price['mdate']]
price = price[['qdate','permno','cfacshr','p','tso']]

price = pd.merge(price, qret, how='left', on=['permno','qdate'])

del qret

# %%time
######################################
# Step 2                             #
# Merge TR13F S34Type1 & 4Type3 sets #
######################################

# First keep first vintage with holdings data for each rdate-mgrno combination
fst_vint = conn.raw_sql("""
                      select rdate, fdate, mgrno::INT, mgrname
                      from tfn.s34type1 
                      """, date_cols=['rdate','fdate']) 

reduce_mem_usage(fst_vint)
# Keep first vintage with holding data for each mgrno-rdate combo
min_fdate = fst_vint.groupby(['mgrno','rdate'])['fdate'].min().reset_index()

# Merge back with the fst_vint data to keep only the first vintage records
fst_vint = pd.merge(fst_vint, min_fdate, how='inner', on=['mgrno','rdate','fdate'])
min_fdate = None

# Sort by mgrno and rdate and create lag_rdate to calculate gap
fst_vint = fst_vint.sort_values(['mgrno', 'rdate'])
fst_vint['lag_rdate']=fst_vint.groupby(['mgrno'])['rdate'].shift(1)

# New code to generate first_report type of variable
# Number of quarters gap between rdate and lag_rdate

fst_vint['rdate_year']=fst_vint.rdate.dt.year
fst_vint['rdate_qtr'] =fst_vint.rdate.dt.quarter

fst_vint['lag_rdate_year']=fst_vint.lag_rdate.dt.year
fst_vint['lag_rdate_qtr'] =fst_vint.lag_rdate.dt.quarter

fst_vint['qtr'] = (fst_vint.rdate_year - fst_vint.lag_rdate_year)*4 + (fst_vint.rdate_qtr - fst_vint.lag_rdate_qtr)

# label first_report flag
fst_vint['first_report'] = ((fst_vint.qtr.isnull()) | (fst_vint.qtr>=2))
fst_vint = fst_vint.drop(['qtr'],axis=1)

# not used in any more calcs so fill NA w/ 0 so can be downcast later
fst_vint['lag_rdate_year'] = fst_vint['lag_rdate_year'].fillna(0)
fst_vint['lag_rdate_qtr'] = fst_vint['lag_rdate_qtr'].fillna(0)

# %%time
# Last report by manager or missing 13F reports in the next quarter(s)
fst_vint = fst_vint.sort_values(['mgrno','rdate'], ascending=[True, False])
fst_vint['lead_rdate']=fst_vint.groupby(['mgrno'])['rdate'].shift(1)

# Number of quarters gap between lead_rdate and rdate
fst_vint['lead_rdate_year']=fst_vint.lead_rdate.dt.year
fst_vint['lead_rdate_qtr'] =fst_vint.lead_rdate.dt.quarter

fst_vint['qtr'] = (fst_vint.lead_rdate_year - fst_vint.rdate_year)*4 + (fst_vint.lead_rdate_qtr - fst_vint.rdate_qtr)


# label last_report flag
fst_vint['last_report'] = ((fst_vint.qtr.isnull()) | (fst_vint.qtr>=2))
fst_vint = fst_vint.drop(['qtr'],axis=1)

fst_vint = fst_vint[(fst_vint['rdate']<=enddate) & (fst_vint['rdate']>=begdate)]\
.drop(['lag_rdate','lead_rdate'], axis=1)

# %%time
######################################
# Step 3                             #
# Extract Holdings and Adjust Shares #
######################################
# Fdate - Vintage Date - is used in shares adjustment
# Map 13F's historical cusip to CRSP's permno information

sql = f"""
  SELECT fdate, mgrno::INT, permno::INT, shares::INT
  FROM tr_13f.s34type3
  INNER JOIN crsp_a_stock.msenames ON (s34type3.cusip = msenames.ncusip)
  WHERE fdate <= '{enddate}'
  GROUP BY fdate, mgrno, permno, shares
"""

# This query produces a LARGE dataset and sometimes pandas requires 10X RAM when not chunked
# using 1Mil chunks and restricting by date(2010) requires about 10GB RAM vs 25GB RAM for no chunking
# RAM required can be reduced even more by lowering chunksize
#s34type3 = conn.raw_sql(sql , date_cols=['fdate']) 
s34type3 = pd.DataFrame() 
iter_s34type3 = pd.read_sql_query(
                    sql=sql,
                    con=conn.connection,
                    coerce_float=True,
                    chunksize=1000000,
                    parse_dates=['fdate'],
)
for chunk in iter_s34type3:
    s34type3 = pd.concat([s34type3, chunk])
del chunk
del iter_s34type3

holdings_v1 = pd.merge(fst_vint, s34type3, how='inner', on=['fdate','mgrno'] )
del s34type3

######################################
# Step 4                             #
# Adjust Shares Using CRSP CFACSHR   #
# Align at Vintage Dates             #
######################################
# These steps use a lot of RAM so be aggressive w/ clearing/dropping data
# Clearing saves about 6GB
reduce_mem_usage(holdings_v1)
holdings = pd.merge(holdings_v1, price[['qdate','permno','cfacshr']], \
                    how='inner', left_on=['permno','fdate'], right_on=['permno','qdate'])
del holdings_v1
# Calculate Adjusted Shares
holdings=holdings.drop(['qdate','fdate'], axis=1)
holdings['shares_adj']=holdings['shares']*holdings['cfacshr']
holdings=holdings.drop(['cfacshr'], axis=1)

# Sanity Checks for Duplicates - Ultimately, Should be 0 Duplicates
holdings = holdings.drop_duplicates(subset=['mgrno','permno','rdate'])

# Keep only observations with shares_adj>0
holdings = holdings[holdings['shares_adj']>0]

# %%time
######################################
# Step 5                             #
# Calculate Institutional Trades     #
# Security-by-Security               #
# trade>0 -> Buy vs trade<0 -> Sale  #
# buysale variable for trade types:  #
#     1 = Initiating Buys            #
#     2 = Incremental (Regular) Buys #
#    -1 = Terminating Sales          #
#    -2 = Regular Sales              #
######################################

t1 = holdings.sort_values(['mgrno','permno','rdate'])
holdings = holdings[['mgrno','permno','rdate','shares_adj']]
# create  phrdate pshares_adj trade and lead lag permno information

# previous holding quarter
t1['phrdate'] = t1.groupby(['mgrno','permno'])['rdate'].shift(1)
# previous quarter shares
t1['pshares_adj'] = t1.groupby(['mgrno','permno'])['shares_adj'].shift(1)
# trade as difference in current and previous quarter shares
t1['trade']=t1['shares_adj'] - t1['pshares_adj']

# quarter gap
# FIXED newer version of pandas was saving Quater Object and not int, convert to int
t1['qtrgap'] = t1['rdate'].dt.to_period('Q').astype(np.int8) - t1['phrdate'].dt.to_period('Q').astype(np.int8)

# lag permno for determining first permno
t1['lpermno'] = t1['permno'].shift(1)

# lead permno for determining last permno
t1['npermno'] = t1['permno'].shift(-1)

# NOTE on program speed:
# The two functions below (modtrade and buysale) are written in the same logic 
# as the original SAS code for determining modified trade quantity and buysale variable. 
# Users can use the "apply" method to run the function on the dataframe. However, this 
# method is very computationally expensive and will take a long time for the code to 
# run. Therefore, it is recommended that users will use the "conditional" methods listed 
# below to calculate these two columns instead. 

# MODTRADE: function to modify trade among based on first_report last_report and qtrgap info
# return value for modified trade
# Terminating records are handled separately

def modtrade(df):
    mt = df['trade']
        
    if df['permno'] != df['lpermno']:
        mt = np.nan

        if not df['first_report']:
            mt = df['shares_adj']
                   
    elif (df['permno'] == df['lpermno']) & (not df['first_report']):
        if df['qtrgap']==1:
            mt = df['trade']
        else:
            mt = df['shares_adj']
    return mt

# BUYSALE: function to assign buysale variable 

def buysale(df):
    bs = np.nan
    if df['permno'] != df['lpermno']:
        if not df['first_report']:
            bs = 1
        
    elif (df['permno'] == df['lpermno']) & (not df['first_report']):
        if df['qtrgap']==1:
            bs = 2*np.sign(df['trade'])
        else:
            bs = 1.5 
        # Mark as 1.5 for further manipulation of adding additional role 
        # for transaction between quarter  
        
    return bs

# It is not recommended to run this step as it takes up too much computational power.
#t1['buysale']  = t1.apply(buysale, axis=1)
#t1['modtrade'] = t1.apply(modtrade, axis=1)

reduce_mem_usage(t1)
reduce_mem_usage(fst_vint)
reduce_mem_usage(holdings)
reduce_mem_usage(price)

# %%time
# Recommended approach: 
# Use condtion combination to replace the two functions modtrade and buysale

# List conditions 
cond1   = (t1.permno!=t1.lpermno)
cond1_1 = (t1.permno!=t1.lpermno) & (~t1.first_report)
cond2_1 = (t1.permno==t1.lpermno) & (~t1.first_report) & (t1.qtrgap==1)
cond2_2 = (t1.permno==t1.lpermno) & (~t1.first_report) & (t1.qtrgap!=1)

# Assign modtrade value based on the conditions listed above
t1['modtrade']             =t1['trade']
t1.loc[cond1, 'modtrade']  =np.nan
t1.loc[cond1_1, 'modtrade']=t1.loc[cond1_1,'shares_adj']
t1.loc[cond2_1, 'modtrade']=t1.loc[cond2_1,'trade']
t1.loc[cond2_2, 'modtrade']=t1.loc[cond2_2,'shares_adj']
#t1['modtrade']= t1['modtrade'].mask(cond1, np.nan)
#t1['modtrade']= t1['modtrade'].mask(cond1_1, t1['shares_adj'])
#t1['modtrade']= t1['modtrade'].mask(cond2_1, t1['trade'])
#t1['modtrade']= t1['modtrade'].mask(cond2_2, t1['shares_adj'])

# Assign buysale value based on the conditions 
t1.loc[cond1_1, 'buysale']=1
t1.loc[cond2_1, 'buysale']=2*np.sign(t1.loc[cond2_1, 'trade'])
t1.loc[cond2_2, 'buysale']=1.5

#t1['buysale'] = np.nan
#t1['buysale'] = t1['buysale'].mask(cond1_1, 1)
#t1['buysale'] = t1['buysale'].mask(cond2_1, 2*np.sign(t1['trade']))
#t1['buysale'] = t1['buysale'].mask(cond2_2, 1.5)

del cond1
del cond1_1 
del cond2_1
del cond2_2

# %%time
# Adjusting rdate for terminating sales records
# These steps require about 12GB RAM
t1['rdate'] = np.where(t1['buysale']==-1, t1['rdate']+pd.offsets.QuarterEnd(1), t1['rdate'])
#t1['rdate'] = t1['rdate'].mask(t1['buysale']==-1, t1['rdate']+pd.offsets.QuarterEnd(1))

# Focusing on cases of intermediate sales - with gaps > 1 qtr 
# Then need to split transaction into 2
t2=t1[(t1.buysale==1.5)]

# avoid SettingWithCopyWarning by recreating these columns
t2 = t2.drop(['rdate','buysale','modtrade'], axis=1)

t2['rdate'] = t2['phrdate']+pd.offsets.QuarterEnd(1)

t2['buysale'] = -1
t2['modtrade'] = -t2['pshares_adj']

# Go back to modify the t1 dataset with buysale variable labeled as 1.5
t1['buysale'] = np.where(t1['buysale']==1.5, 1, t1['buysale'])
#t1['buysale'] = t1['buysale'].mask(t1['buysale']==1.5, 1)

# handle terminating sales
t3 = t1[(t1.permno != t1.npermno) & (t1.last_report == False)]

t3 = t3.drop(['buysale','modtrade'], axis=1)

t3['rdate'] = t3['rdate']+pd.offsets.QuarterEnd(1)
t3['modtrade'] = -t3['shares_adj']
t3['buysale'] = -1
# Append t1 t2 and t3 to create the complete trades output
#appending is expensive so lets drop unneeded cols first
t1 = t1[['rdate','mgrno','permno','modtrade','buysale']]
t2 = t2[['rdate','mgrno','permno','modtrade','buysale']]
t3 = t3[['rdate','mgrno','permno','modtrade','buysale']]
trades = t1.append([t2,t3])
del t1
del t2
del t3
trades = trades[(trades.modtrade != 0)&(trades.modtrade.notna())&(trades.buysale.notna())]
trades = trades[['rdate','mgrno','permno','modtrade','buysale']]
trades = trades.rename(columns={'modtrade':'trade'})

#trades.to_csv('~/pytradesv2.csv')

######################################
# Step 6                             #
# Calculate Assets, Total Buys, and  #
# Total Sales per Institution Each   #
# Quarter                            #
######################################

# Get Total Assets and Portfolio Returns from Holdings  
# Assuming Buys and Sales Are Executed at Calendar Quarter Ends

_holdings = holdings[['mgrno','permno','rdate','shares_adj']]
_price    = price[['permno','qdate','p','qret']]
_assets   = pd.merge(_holdings, _price, \
                  how='inner', left_on=['permno','rdate'], right_on=['permno','qdate'])

del holdings
del price
del _holdings

# create intermediate variables before summing by manager and quarter

# dollar held in each stock per quarter per manager
_assets['hold_per_stock'] = _assets['shares_adj']*_assets['p']/1000000
# dollar held projected to next quarter assuming same shares held
_assets['next_value'] = _assets['shares_adj']*_assets['p']*_assets['qret']
# dollar held curent quarter
_assets['curr_value'] = _assets['shares_adj']*_assets['p']

# sum values across different stocks by a manager in a quarter
hold_per_stock = _assets.groupby(['mgrno','rdate'])['hold_per_stock'].sum().reset_index()
next_qtr = _assets.groupby(['mgrno','rdate'])['next_value'].sum().reset_index()
curr_qtr = _assets.groupby(['mgrno','rdate'])['curr_value'].sum().reset_index()

# Forward portfolio return
pret = pd.merge(next_qtr, curr_qtr, how='inner', on=['mgrno','rdate'])
pret['pret'] = pret['next_value']/pret['curr_value']
pret = pret[['mgrno','rdate','pret']]

assets = pd.merge(hold_per_stock, pret, how='inner',on=['mgrno','rdate'])

# Total portfolio Assets
assets = assets.rename(columns={'hold_per_stock':'assets'})

import gc
del _assets
del hold_per_stock
del next_qtr
del curr_qtr
del pret
gc.collect()

# Aggregate Total Buys and Sales per Institution Every Quarter 

# create intermediate variables first
_flows = pd.merge(trades, _price, how='inner', \
                  left_on=['permno','rdate'], right_on=['permno','qdate'])
del trades
# dollar amount buys per stock by a manager in a quarter
_flows['tbuys']  = _flows['trade']*(_flows['trade']>0) * _flows['p']/1000000
# dollar amount sells per stock by a manager in a quarter
_flows['tsales'] = (-1)*_flows['trade']*(_flows['trade']<0) * _flows['p']/1000000
# net gain from trades per stock 
_flows['tgain']  = _flows['trade']*_flows['p']*_flows['qret']/1000000

# sum values across different stocks by a manager in a quarter
tbuys  = _flows.groupby(['mgrno','rdate'])['tbuys'].sum().reset_index()
tsales = _flows.groupby(['mgrno','rdate'])['tsales'].sum().reset_index()
tgain  = _flows.groupby(['mgrno','rdate'])['tgain'].sum().reset_index()

ttran = pd.merge(tbuys, tsales, how='inner', on =['mgrno','rdate'])

# Flows dataframe
flows = pd.merge(ttran, tgain, how='inner',on=['mgrno','rdate'])

# %%time
######################################
# Step 7                             #
# Calculate Net Flows and Turnover   #
######################################

fst_vint = fst_vint.sort_values(['mgrno','rdate'])
fst_vint = fst_vint.drop_duplicates(subset=['mgrno','rdate'])

# inner join fst_vint and assets dataframes then left join with flows
_agg1 = pd.merge(fst_vint, assets, how='inner', on =['mgrno','rdate'])
del fst_vint
del assets
_agg1 = _agg1.drop(['fdate'], axis=1)
aggregates = pd.merge(_agg1, flows, how='left', on=['mgrno','rdate'])
del flows

# assets compound value
aggregates['assets_comp'] = aggregates['assets']*(1+aggregates['pret'])

aggregates = aggregates.sort_values(['mgrno','rdate'])
# lag asset compound value
aggregates['lassets_comp'] = aggregates.groupby(['mgrno'])['assets_comp'].shift(1)
# lag asset value
aggregates['lassets'] = aggregates.groupby(['mgrno'])['assets'].shift(1)

# Trade Returns = Returns on Purchases - Forgone Returns on Sales
aggregates['tgainret'] = aggregates['tgain']/(aggregates['tbuys'] + aggregates['tsales'])
aggregates['netflows'] = aggregates['assets'] - aggregates['lassets_comp']

# Three Types of Turnover Measures

# Carhart (1997) Turnover Definition
aggregates['turnover1'] = \
(aggregates[['tbuys', 'tsales']].min(axis=1)) / (aggregates[['assets', 'lassets']].mean(axis=1))

# Adding Back Net Flows and Redemptions
aggregates['turnover2'] = \
(aggregates[['tbuys', 'tsales']].min(axis=1) + aggregates['netflows'].abs().fillna(0)) \
/ aggregates['lassets']

# or, Alternatively
aggregates['turnover3'] = \
(aggregates['tbuys'].fillna(0)+aggregates['tsales'].fillna(0)-aggregates['netflows'].abs().fillna(0))\
/ aggregates['lassets']

# Assign missing values for first_report records
aggregates['netflows']=np.where(aggregates['first_report'], np.nan, aggregates['netflows'])
aggregates['tgainret']=np.where(aggregates['first_report'], np.nan, aggregates['tgainret'])
aggregates['turnover1']=np.where(aggregates['first_report'], np.nan, aggregates['turnover1'])
aggregates['turnover2']=np.where(aggregates['first_report'], np.nan, aggregates['turnover2'])
aggregates['turnover3']=np.where(aggregates['first_report'], np.nan, aggregates['turnover3'])

aggregates=aggregates.drop(['assets_comp', 'lassets_comp', 'lassets'], axis=1)

aggregates.shape

aggregates = aggregates.round({'assets':1, 'pret':4, 'tbuys':1, 'tsales':1, 'tgain':1, 'tgainret':4, 'netflows':1, 'turnover1':4, 'turnover2':4, 'turnover3':4})
aggregates

# 13F Institutions with Equity Outflows of more than $20 Billion in the Last Quarter of 2008
#
last_qrt_2008 = aggregates.loc[aggregates['rdate'] =='2008-12-31']
last_qrt_2008 = last_qrt_2008[['rdate','mgrno','mgrname','assets','pret','tbuys','tsales','tgain','netflows','turnover1']].sort_values('netflows')

last_qrt_2008.head(19).style.format({
    "rdate": lambda t: t.strftime("%Y-%m-%d"),
    'assets':'${:,.0f}'.format, 
    'tbuys':'${:,.0f}'.format, 
    'tsales':'${:,.0f}'.format, 
    'tgain':'${:,.0f}'.format, 
    'netflows':'${:,.0f}'.format, 
    'pret': '{:,.2%}'.format,
    'turnover1': '{:,.2%}'.format,
}

)

aggregates.to_csv('~/pyaggregates.csv')

currentDT_end = datetime.datetime.now()
print (str(currentDT_end))

print('Time Spent:', currentDT_end-currentDT_start)

# Lets see max RAM used (VmPeak) and current RAM used
file = open("/proc/self/status", "r")
for line in file:
    if 'VmPeak' in line or 'VmRSS' in line:
        l = line.split()
        print(f"{l[0]}\t {l[1]} {l[2]}\t {round(int(l[1])/1024/1024, 2)} GB")
