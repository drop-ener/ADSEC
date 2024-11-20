import setuptools

#with open("README.md", "r") as fh:
#    long_description = fh.read()

setuptools.setup(
    name="adsec-flow",
    version="0.1",
    author="Xiaoze Yuan",
    author_email="yuanxiaoze@dp.tech",
    description="ADSorption Energy Calculation",
    #long_description=long_description,
    #long_description_content_type="text/markdown",
    #url="https://github.com/deepmodeling/APEX.git",
    packages=setuptools.find_packages(),
    install_requires=[
        "numpy<2.0.0",
        "pydflow>=1.7.83",
        "pymatgen>=2023.8.10",
        'pymatgen-analysis-defects>=2023.8.22',
        "dpdata>=0.2.13",
        "dpdispatcher",
        "phonopy",
        "plotly",
        "dash",
        "dash_bootstrap_components",
        "seekpath",
        "fpop>=0.0.7",
        "boto3",
        "pymongo",
        "apex-flow==1.2.8",
        "multiprocess"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
    entry_points={'console_scripts': [
         'adsec = adsec.__main__:main',
     ]}
)
