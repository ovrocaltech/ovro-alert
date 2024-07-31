import healpy as hp
import numpy as np
import matplotlib.pyplot as plt
import astropy.units as u
from astropy.coordinates import EarthLocation, AltAz, SkyCoord
from astropy.time import Time
import argparse

def main(filename, utc_time, output_base_filename):
    # Load the HEALPix map
    hpx, header = hp.read_map(filename, h=True)

    npix = len(hpx)
    sky_area = 4 * 180**2 / np.pi
    pixel_area = sky_area / npix

    nside = hp.npix2nside(npix)

    i = np.flipud(np.argsort(hpx))
    sorted_credible_levels = np.cumsum(hpx[i])
    credible_levels = np.empty_like(sorted_credible_levels)
    credible_levels[i] = sorted_credible_levels

    credible_area = np.sum(credible_levels <= 0.9) * hp.nside2pixarea(nside, degrees=True)
    print(f"90% credible region area: {credible_area:.2f} square degrees")

    # Define the observatory's ECEF coordinates
    x = -2409261.7339418 * u.m
    y = -4477916.56772157 * u.m
    z = 3839351.13864434 * u.m
    observatory = EarthLocation.from_geocentric(x, y, z)

    # Convert the input UTC time to astropy Time object
    time = Time(utc_time, format='isot', scale='utc')

    # Create AltAz frame for the observatory
    frame = AltAz(obstime=time, location=observatory)

    # Look up (celestial) spherical polar coordinates of HEALPix grid
    theta, phi = hp.pix2ang(nside, np.arange(npix))

    # Convert to RA, Dec
    radecs = SkyCoord(ra=phi * u.rad, dec=(0.5 * np.pi - theta) * u.rad, frame='icrs')

    # Transform grid to alt/az coordinates at the observatory
    altaz = radecs.transform_to(frame)

    # Define the altitude threshold
    ALT_THRESHOLD = 5 * u.deg

    # Create a mask for pixels with alt >= ALT_THRESHOLD
    mask = altaz.alt >= ALT_THRESHOLD

    # Create a new map with 0s and 1s based on the inverted mask
    mask_map = np.zeros_like(hpx)
    mask_map[mask] = 1

    # Create a mask for the 90% credible region above the altitude threshold
    credible_90_mask = (credible_levels <= 0.9) & mask

    # Calculate the area of the 90% credible region above the horizon
    credible_90_area_above_horizon = np.sum(credible_90_mask) * hp.nside2pixarea(nside, degrees=True)
    print(f"90% credible region area above the horizon: {credible_90_area_above_horizon:.2f} square degrees")

    # Create a new map with only the 90% credible region above the horizon
    credible_90_map_above_horizon = np.zeros_like(hpx)
    credible_90_map_above_horizon[credible_90_mask] = hpx[credible_90_mask]

    # Plot and save the original sky map
    fig = plt.figure(figsize=(15, 10))
    hp.projview(hpx, fig=fig, graticule=True, graticule_labels=True, projection_type='mollweide', title='Original Sky Map')
    hp.graticule()
    fig.canvas.draw()
    plt.savefig(f"{output_base_filename}_original_sky_map.png")
    plt.close(fig)

    # Plot and save the masked sky map
    fig = plt.figure(figsize=(15, 10))
    hp.projview(mask_map, fig=fig, graticule=True, graticule_labels=True, projection_type='mollweide', title='Masked Sky Map', cmap='Reds')
    hp.graticule()
    fig.canvas.draw()
    plt.savefig(f"{output_base_filename}_masked_sky_map.png")
    plt.close(fig)

    # Plot and save the 90% credible region above the horizon
    fig = plt.figure(figsize=(15, 10))
    hp.projview(credible_90_map_above_horizon, fig=fig, graticule=True, graticule_labels=True, projection_type='mollweide', title='90% Credible Region Above Horizon', cmap='Greens')
    hp.graticule()
    fig.canvas.draw()
    plt.savefig(f"{output_base_filename}_credible_90_above_horizon.png")
    plt.close(fig)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process a FITS skymap file and save the filtered images as PNGs. It also prints the full 90th percentile area and the area above the horizon.')
    parser.add_argument('filename', type=str, help='The path to the FITS file to be processed')
    parser.add_argument('utc_time', type=str, help='The observation time in UTC format (e.g., "2024-07-01T12:34:56")')
    parser.add_argument('output_base_filename', type=str, help='The base path to save the output PNG files')
    args = parser.parse_args()

    main(args.filename, args.utc_time, args.output_base_filename)
