'''The tables with pulsar information (csv files) are taken from K.Stovall et al. 2018, https://arxiv.org/pdf/1410.7422.pdf '''

import argparse
from itertools import cycle
from astropy.time import Time
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from astroquery.simbad import Simbad
from astropy import coordinates as coord
from astropy import units as u
from astropy.coordinates import EarthLocation, AltAz, SkyCoord
import pandas as pd
import os

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# The path to the pulsar flux measurements CSV file
flux_path = os.path.join(script_dir, 'pulsar_flux_measurements.csv')
dm_path = os.path.join(script_dir, 'pulsar_dm_measurements.csv')

def pulsar_data_generate(flux_path=flux_path, dm_path=dm_path):
    '''
    Generate pulsar data from flux and DM measurements CSV files.
    
    Parameters:
        flux_path (str): Path to the pulsar flux measurements CSV file.
        dm_path (str): Path to the pulsar DM measurements CSV file.
    
    Returns:
        pulsar_data (dict): Dictionary containing pulsar data.
    '''
    flux_df = pd.read_csv(flux_path)
    dm_df = pd.read_csv(dm_path)
    pulsar_data = {}

    # Process the flux measurements
    for pulsar in flux_df['Pulsar'].unique():
        # Prefix "PSR " to the pulsar name
        pulsar_name = "PSR " + pulsar
        
        # Find the row with the maximum frequency for the current pulsar
        pulsar_flux_df = flux_df[flux_df['Pulsar'] == pulsar]
        max_freq_idx = pulsar_flux_df['ν (MHz)'].idxmax()
        max_freq_row = pulsar_flux_df.loc[max_freq_idx]
        
        # Extract the flux, frequency, and w50, removing values in parentheses
        flux = float(max_freq_row['S_ν (mJy)'].split('(')[0])
        freq = max_freq_row['ν (MHz)']
        w50 = float(max_freq_row['w_50 (phase)']) if 'w_50 (phase)' in max_freq_row and pd.notnull(max_freq_row['w_50 (phase)']) else None
        
        # Initialize dictionary for the pulsar if not exists
        pulsar_data[pulsar_name] = {'flux': flux, 'freq': freq}
        if w50 is not None:
            pulsar_data[pulsar_name]['w50'] = w50

    # Process the DM measurements
    for index, row in dm_df.iterrows():
        pulsar = "PSR " + row['Pulsar']
        P = row['P (s)']
        DM = float(row['DM_ATNF (pc cm^-3)'].split('(')[0])
        
        # Update the dictionary for the pulsar if exists
        if pulsar in pulsar_data:
            pulsar_data[pulsar]['P'] = P
            pulsar_data[pulsar]['DM'] = DM

    return pulsar_data

# LWA location
observatory = EarthLocation(lat=34.07*u.deg, lon=-107.63*u.deg, height=1222*u.m)
pulsar_data = pulsar_data_generate()

def get_pulsar_info(pulsar_name, observe_time):
    '''
    Get information about a pulsar at a specific observation time (including altitude, RA and Dec).
    
    Parameters:
        pulsar_name (str): Name of the pulsar.
        observe_time (astropy.time.Time): Observation time.
    
    Returns:
        pulsar_info (dict): Dictionary containing pulsar information.
    '''
    # Verify that we have data for this pulsar
    if pulsar_name not in pulsar_data:
        print(f'No data for {pulsar_name}!')
        return None
    
    # Query Simbad for coordinates
    customSimbad = Simbad()
    customSimbad.add_votable_fields('coordinates')
    result_table = customSimbad.query_object(pulsar_name)
    
    # Extract coordinates
    ra = result_table['RA'][0]
    dec = result_table['DEC'][0]
    
    # Convert coordinates to SkyCoord object
    c = SkyCoord(ra, dec, unit=(u.hourangle, u.deg), frame='icrs')
    
    # Convert observation time to AltAz frame at the observatory location
    altaz_frame = AltAz(obstime=observe_time, location=observatory)
    
    # Transform the SkyCoord to the AltAz frame
    altaz = c.transform_to(altaz_frame)
    
    # Combine data into a single dictionary
    pulsar_info = {
        'name': pulsar_name,
        'ra': c.ra.deg,
        'dec': c.dec.deg,
        'flux (mJy) @ highest freq': pulsar_data[pulsar_name]['flux'],
        'highest freq (MHz)': pulsar_data[pulsar_name]['freq'],
        'DM (pc cm^-3)': pulsar_data[pulsar_name]['DM'],
        'P (s)': pulsar_data[pulsar_name]['P'],
        'w50': pulsar_data[pulsar_name]['w50'],
    }

    # Add Alt and Az to the output dictionary
    pulsar_info['Alt (deg)'] = altaz.alt.deg
    pulsar_info['Az (deg)'] = altaz.az.deg
    
    return pulsar_info

def process_pulsars(observe_time, plot, bright):
    '''
    Process pulsars for observation.
    
    Parameters:
        observe_time (astropy.time.Time): Observation time.
        plot (bool): Whether to plot pulsar altitudes.
        bright (bool): Whether to use only bright pulsars for observation.
    '''
    # Filter for bright pulsars if requested
    if bright:
        bright_pulsars = ['PSR B1133+16', 'PSR B0329+54', 'PSR B0628-28', 'PSR B0834+06', 'PSR B1508+55', 'PSR B1604-00', 'PSR B1822-09', 'PSR B1919+21']
        pulsar_data_filtered = {k: v for k, v in pulsar_data.items() if k in bright_pulsars}
    else:
        pulsar_data_filtered = pulsar_data
    
    # Sort and print the pulsars with alt>10 by their flux at the observation time
    pulsar_infos = [get_pulsar_info(pulsar_name, observe_time) for pulsar_name in pulsar_data_filtered.keys()]
    pulsar_infos = sorted([info for info in pulsar_infos if info['Alt (deg)'] > 10],
                          key=lambda info: info['Alt (deg)'], reverse=True)

    for info in pulsar_infos:
        print(f"{info['name']} at (RA, Dec) = ({info['ra']}, {info['dec']})")
        print(f"\t Altitude: {info['Alt (deg)']:.2f} deg, Flux at highest freq: {info['flux (mJy) @ highest freq']} mJy, Highest freq: {info['highest freq (MHz)']} MHz, DM: {info['DM (pc cm^-3)']:.2f} pc cm^-3, Period: {info['P (s)']:.2f} s, w50: {info['w50']}")

    times = observe_time + np.arange(-12*2, 12*2)*30*u.min

    alt_data = {}

    for pulsar_name in pulsar_data_filtered.keys():
        altitudes = []
        for time in times:
            info = get_pulsar_info(pulsar_name, time)
            altitudes.append(info['Alt (deg)'])
        alt_data[pulsar_name] = altitudes

    if plot: # Create plot
        plt.figure(figsize=(10,6))

        color_cycle = cycle(plt.rcParams['axes.prop_cycle'].by_key()['color'])  

        for pulsar_name, altitudes in alt_data.items():
            altitudes = np.array(altitudes)

            # Check if the pulsar is above 10 degrees at the observation time
            if get_pulsar_info(pulsar_name, observe_time)['Alt (deg)'] > 10:
                color = next(color_cycle) 
                plt.plot_date(times.plot_date, altitudes, fmt='-', color=color, label=pulsar_name)

        # Add a vertical line representing the observation time
        plt.axvline(x=observe_time.plot_date, color='r', linestyle='--')

        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.gcf().autofmt_xdate()

        plt.xlabel('Time (UTC)')
        plt.ylabel('Altitude (deg)')
        plt.legend(loc='best')
        plt.grid(True)
        plt.show()


def main():
    '''
    Main function.
    '''
    # Create an argument parser
    parser = argparse.ArgumentParser(description='Pulsars for LWA observation test')

    # Add argument for observation time
    parser.add_argument('-t', '--time', type=str, required=False,
                        help='Observation time in the format YYYY-MM-DDTHH:MM:SS (UTC). Default is now.')
    
    # Add argument for enabling/disabling plotting
    parser.add_argument('--plot', action='store_true',
                        help='Enable plotting of pulsar altitudes. Disabled by default.')

    # Add argument for using only bright pulsars
    parser.add_argument('--bright', action='store_true', default=True,
                    help=f'Use only bright pulsars for observation. They include: PSR B1133+16, PSR B0329+54, PSR B0628-28, PSR B0834+06, PSR B1508+55, PSR B1604-00, PSR B1822-09, PSR B1919+21')

    parser.add_argument('--all', action='store_false', dest='bright',
                    help='Include all pulsars for observation, not just the bright ones.')

    # Parse the arguments
    args = parser.parse_args()

    # Convert the observation time string to an Astropy Time object
    if args.time is not None:
        observe_time = Time(args.time)
    else:
        print('Using current time')
        observe_time = Time.now()

    # Call the function to process the pulsars
    process_pulsars(observe_time, plot=args.plot, bright=args.bright)


if __name__ == '__main__':
    main()





