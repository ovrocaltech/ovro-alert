from setuptools import setup

setup(
    name="ovro-alert",
    description="Code and services for sending, receiving, and using astronomical alerts at OVRO",
    url="https://github.com/ovrocaltech/ovro-alert",
    python_requires=">=3.6",
    use_scm_version={
        "version_scheme": "post-release",
        "local_scheme": "no-local-version",
    },
    setup_requires=["setuptools_scm"],
    install_requires=[
        "requests",
    ],
    packages=["ovro_alert"],
    zip_safe=False,
)
