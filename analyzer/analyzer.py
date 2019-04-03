import os
import sys
import configparser

import matplotlib
matplotlib.use('Agg') # Don't try to use X forwarding for plots
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

import pandas as pd
import numpy as np
from root_pandas import read_root
from scipy.optimize import curve_fit
import ROOT


### Insert path to most recent directory with fast data

_,mostRecentDir = sys.argv


simulation_files = ('NULL','MC_ti44_modulation.root', 'MC_cs137_modulation.root', 'MC_co60_modulation.root')


def append_dfs():
    rootf=[]
    for file in os.listdir(mostRecentDir):
	    if file.endswith('.root'):
		    rootf.append(file)
    if len(rootf)>1:
	    framesroot = [read_root(mostRecentDir+'/'+rf, columns=['channel','time','error','integral']) for rf in rootf]
	    df = pd.concat(framesroot,axis=0)
    else:
	    df = read_root(mostRecentDir+'/'+rootf[0], columns=['channel','time','error','integral'])
    return df

def timedelta(df):
    df['time'] = df['time'] - 2208988800
    df['time'] = pd.to_datetime(df['time'], unit = 's')
    return (df['time'].min()-df['time'].max()).seconds

def gauss(x, *p):
    A, mu, sigma = p
    return A*np.exp(-(x-mu)**2/(2.*sigma**2))

def triple_gauss(x, *p):
    A1, mu1, sigma1 = p
    return A1*np.exp(-(x-mu1)**2/(2.*sigma1**2)) + A2*np.exp(-(x-mu2)**2/(2.*sigma2**2)) + A3*np.exp(-(x-mu3)**2/(2.*sigma3**2))

def specdf(df,channel):
    df = df[(df['channel']==channel)][['time','integral']]
    td = timedelta(df)
    binnage = [i for i in range( int( int(df['integral'].min()) - ( int(df['integral'].min())%5)),int( int(df['integral'].max()) - ( int(df['integral'].max())%5)), 5)]
    count, bin_edges = np.histogram(df['integral'].values,bins=binnage)
    unpacked_hist = count.astype('float64')/(float(td))
    return unpacked_hist,bin_edges[:-1]

class HistogramFile(object):

    def __init__(self, filename):
        self.filename = filename

    def __enter__(self):
        self.file = ROOT.TFile.Open(self.filename, 'read')
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        self.file.Close()

    def get_histogram(self, name):
        """Return the histogram identified by name from the file.
        """
        # The TFile::Get() method returns a pointer to an object stored in a ROOT file.
        hist = self.file.Get(name)
        if hist:
            return hist
        else:
            raise RuntimeError('Unable to retrieve histogram named {0} from {1}'.format(name, self.filename))
    
def compton_simulation(filename):
    with HistogramFile(filename) as f:
        hist = f.get_histogram('h2;1')
        unpacked_hist = []
        for i in range(0,hist.GetNbinsX()):
             unpacked_hist.append(hist.GetBinContent(i))
        return np.array(unpacked_hist), np.array([5*e for e in range(600)])


def subtract_compton(df,channel):
    sim_count, sim_energy = compton_simulation(simulation_files[channel//2])
    fast_count,fast_energy = specdf(df,channel)
    bg_count, bg_energy = specdf(df,0)
    ### Range fixing for simulation data
    sim_energy = np.array(filter(lambda x: x >= min(fast_energy),sim_energy))
    if len(sim_count) != len(sim_energy):
        sim_count = sim_count[len(sim_count)-len(sim_energy):]
    sim_energy = np.array(filter(lambda x: x <= max(fast_energy),sim_energy))
    if len(sim_count) != len(sim_energy):
        sim_count = sim_count[:(len(sim_energy)-len(sim_count))]
    ##
    ### Range fixing for background data
    if len(bg_energy) >= len(fast_energy):
        bg_energy = np.array(filter(lambda x: x >= min(fast_energy),bg_energy))
        if len(bg_count) != len(bg_energy):
            bg_count = bg_count[len(bg_count)-len(bg_energy):]
        bg_energy = np.array(filter(lambda x: x <= max(fast_energy),bg_energy))
        if len(bg_count) != len(bg_energy):
            bg_count = bg_count[:(len(bg_energy)-len(bg_count))]
    else:
        print(min(bg_energy),max(bg_energy),min(fast_energy),max(fast_energy))
        if bg_energy[-1] != fast_energy[-1]:
            bg_count = np.append(bg_count,np.multiply([i for i in range(max(bg_energy),max(fast_energy),5)],0))
            bg_energy = np.append(bg_energy,[i for i in range(max(bg_energy),max(fast_energy),5)])
        if bg_energy[0] != fast_energy[0]:    
            bg_count = np.append(np.multiply([i for i in range(min(fast_energy),min(bg_energy),5)],0),bg_count)
            bg_energy = np.append([i for i in range(min(fast_energy),min(bg_energy),5)],bg_energy)
    ##
    if channel == 2 or channel == 3:
        ratio = max(fast_count[int(np.where(fast_energy ==570)[0]):int(np.where(fast_energy == 800)[0])])/max(sim_count[int(np.where(sim_energy == 570)[0]):int(np.where(sim_energy == 800)[0])])
    elif channel == 4 or channel == 5:
        ratio = max(fast_count[int(np.where(fast_energy ==150)[0]):int(np.where(fast_energy == 250)[0])])/max(sim_count[int(np.where(sim_energy == 150)[0]):int(np.where(sim_energy == 250)[0])])
    else:
        ratio = max(fast_count[int(np.where(fast_energy ==850)[0]):int(np.where(fast_energy == 1000)[0])])/max(sim_count[int(np.where(sim_energy == 850)[0]):int(np.where(sim_energy == 1000)[0])])
    sim_count = sim_count*ratio
    
    print(len(bg_count))
    print(len(fast_count))

    fast_count = np.subtract(fast_count,bg_count)
    return np.subtract(fast_count,sim_count),fast_energy,sim_count,fast_count


dataframe = append_dfs()
dataframe = dataframe[(dataframe['integral'] >= 0) & (dataframe['integral'] <= 3000) & (dataframe['error'] == 0)][['time','integral','channel']]

for chn in range(2,3): 
    final,energy,simulation_count,count = subtract_compton(dataframe,chn)


plt.figure()
plt.scatter(energy,simulation_count,c='k',s=1)
plt.scatter(energy,count,c='r',s=1)
plt.scatter(energy,final,c='green',s=1)
plt.axhline(y=0,c='k')
plt.xlim(300,1500)
plt.savefig('compton.png')
plt.close()

