import sys
import argparse
from astropy.time import Time
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from astroquery.simbad import Simbad
from astropy import coordinates as coord
from astropy import units as u
from astropy.coordinates import EarthLocation, AltAz, SkyCoord

# LWA location
observatory = EarthLocation(lat=34.07*u.deg, lon=-107.63*u.deg, height=1222*u.m)

# Dictionary of known fluxes, DMs, periods, and w50
# see https://arxiv.org/pdf/1410.7422.pdf
pulsar_data = {
    'PSR B1133+16': {
        'flux': 5120, 
        'DM': 4.85,  
        'P': 1.188,
        'w50': 0.02
    },
    'PSR B0329+54': {
        'flux': 3060,
        'DM': 26.8,
        'P': 0.71,
        'w50': 0.023
    },
    'PSR B0628-28': {
        'flux': 5410,
        'DM': 34.5,
        'P': 1.24,
        'w50': 0.059
    },
    'PSR B0834+06': {
        'flux': 4790,
        'DM': 12.89,
        'P': 1.27,
        'w50': 0.023
    },
    'PSR B1508+55': {
        'flux': 2350,
        'DM': 19.6,
        'P': 0.74,
        'w50': 0.016
    },
    'PSR B1604-00': {
        'flux': 990,
        'DM': 10.68,
        'P': 0.42,
        'w50': 0.023
    },
    'PSR B1822-09': {
        'flux': 1860,
        'DM': 19.38,
        'P': 0.77,
        'w50': 0.027
    },
    'PSR B1919+21': {
        'flux': 1730,
        'DM': 12.44,
        'P': 1.34,
        'w50': 0.02
    }
  
}

def get_pulsar_info(pulsar_name, observe_time):
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
        'flux (mJy) @ 65 MHz': pulsar_data[pulsar_name]['flux'],
        'DM (pc cm^-3)': pulsar_data[pulsar_name]['DM'],
        'P (s)': pulsar_data[pulsar_name]['P'],
        'w50': pulsar_data[pulsar_name]['w50'],
    }
    
    

    # Add Alt and Az to the output dictionary
    pulsar_info['Alt (deg)'] = altaz.alt.deg
    pulsar_info['Az (deg)'] = altaz.az.deg
    
    return pulsar_info

def process_pulsars(observe_time):

    # Sort and print the pulsars with alt>10 by their flux at the observation time
    pulsar_infos = [get_pulsar_info(pulsar_name, observe_time) for pulsar_name in pulsar_data.keys()]
    pulsar_infos = sorted([info for info in pulsar_infos if info['Alt (deg)'] > 10], key=lambda info: info['flux (mJy) @ 65 MHz'], reverse=True)

    for info in pulsar_infos:
        print(f"Name: {info['name']}, Altitude: {info['Alt (deg)']:.2f} deg, Flux: {info['flux (mJy) @ 65 MHz']} mJy, DM: {info['DM (pc cm^-3)']:.2f} pc cm^-3, Period: {info['P (s)']:.2f} s, w50: {info['w50']}")


    times = observe_time + np.arange(-12*2, 12*2)*30*u.min


    alt_data = {}


    for pulsar_name in pulsar_data.keys():
        altitudes = []
        for time in times:
            info = get_pulsar_info(pulsar_name, time)
            altitudes.append(info['Alt (deg)'])
        alt_data[pulsar_name] = altitudes


    plt.figure(figsize=(10,6))


    for pulsar_name, altitudes in alt_data.items():
        altitudes = np.array(altitudes)

        # Check if the pulsar is above 10 degrees at the observation time
        if get_pulsar_info(pulsar_name, observe_time)['Alt (deg)'] > 10:
            color = next(plt.gca()._get_lines.prop_cycler)['color']
            plt.plot_date(times.plot_date, altitudes, fmt='-', color=color, label=pulsar_name)

    # Add a vertical line representing the observation time
    plt.axvline(x=observe_time.plot_date, color='r', linestyle='--')

    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.gcf().autofmt_xdate()

    plt.xlabel('Time')
    plt.ylabel('Altitude (deg)')
    plt.legend(loc='best')
    plt.grid(True)
    plt.show()



def main():
    # Create an argument parser
    parser = argparse.ArgumentParser(description='bright pulsars for LWA observation test')

    # Add argument for observation time
    parser.add_argument('-t', '--time', type=str, required=True,
                        help='observation time in the format YYYY-MM-DDTHH:MM:SS (UTC)')

    # Parse the arguments
    args = parser.parse_args()

    # Convert the observation time string to an Astropy Time object
    observe_time = Time(args.time)

    # Call the function to process the pulsars
    process_pulsars(observe_time)


if __name__ == '__main__':
    main()





