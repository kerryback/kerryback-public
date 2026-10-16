##########################################
# Time Series of Number of Institutions  #
# by Manager Type                        #
# November 2018                          #
# Qingyi (Freda) Song Drechsler          #
##########################################

import pandas as pd
import numpy as np
import datetime as dt
import wrds
import psycopg2 
import matplotlib.pyplot as plt

###################
# Connect to WRDS #
###################
conn=wrds.Connection()

# Read S34Type1 Dataset
# rdate = Holdings Report Date
# fdate = Vintage Date
s34type1 = conn.raw_sql("""
                    select fdate, rdate, typecode, mgrno 
                    from tfn.s34type1 
                    where typecode IS NOT NULL
                    """, date_cols = ['fdate', 'rdate'])
s34type1[['typecode','mgrno']]=s34type1[['typecode','mgrno']].astype(int)
s34type1 = s34type1[s34type1['rdate']==s34type1['fdate']]

# Count the number of institutions by typecode
instcounts = s34type1.groupby(['rdate','typecode'])['mgrno'].count()\
.to_frame().reset_index()
instcounts=instcounts.rename(columns={'mgrno':'numero'})
instcounts.head()

# Reshape (transpose) the table 
# Report number by typecode per column
ts = instcounts.pivot(index='rdate', columns='typecode', values='numero')

# Rename the columns by label
ts = ts.rename(columns={1:'Bank',\
                        2:'Insurance',\
                        3:'Mutual Funds', \
                        4:'Investment Advisors',\
                        5:'Others'}).reset_index()

# Fill in 0 for missing observation
ts = ts.fillna(0)
ts.head(20)

# Calculate Total by adding up all categories
ts['Total']=ts['Bank']+ts['Insurance']+ts['Mutual Funds']+ts['Investment Advisors']+ts['Others']

# Year and Month information from rdate
ts['Month']=ts['rdate'].dt.month
ts['Year']=ts['rdate'].dt.year

ts=ts.set_index('rdate')

ts.head(20)

# Results at Year End
ts_yend = ts[ts['Month']==12].drop(['Month'],axis=1)
ts_yend.head()

ts_yend.to_csv('~/13f_intro.csv')

ts = ts.drop(['Month', 'Year'], axis=1)

# Plot the time series of the charts
ts.plot(kind='line', title = 'Time Series of the Number of Institutions by Manager Type',\
        linewidth=4, figsize=(12,8), fontsize=15)
