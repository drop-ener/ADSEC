'''
This modules contains functions that return default settings for various
function and queries used in GASpy and its submodules. We keep everything
functions so that you don't modify some settings in one location and have it
accidentally affect the setting in a different location.
'''

import warnings
from collections import OrderedDict
from ase import Atoms
import ase.constraints


def pp_version():
    ''' Vasp pseudopotential version '''
    return '5.4'


def logfile_settings(keep_all_logfiles=False):
    '''Whether to keep electronic log files (CHG, CHGCAR, WAVECAR)'''

    logfile_settings = {'lwave': keep_all_logfiles,
                        'lcharg': keep_all_logfiles}

    return logfile_settings


def xc_settings(xc='rpbe'):
    '''
    A dictionary whose keys are some typical sets of exchange correlationals
    and whose values are dictionaries with the corresponding pseudopotential
    (pp), generalized gradient approximations (ggas), and other pertinent
    information.  Credit goes to John Kitchin who wrote vasp.Vasp.xc_defaults,
    which we copied and put here.
    '''
    xc_settings = {'lda': OrderedDict(pp='LDA'),
                   # GGAs
                   'gga': OrderedDict(pp='GGA'),
                   'pbe': OrderedDict(pp='PBE'),
                   'revpbe': OrderedDict(pp='LDA', gga='RE'),
                   'rpbe': OrderedDict(gga='RP', pp='PBE'),
                   'am05': OrderedDict(pp='LDA', gga='AM'),
                   'pbesol': OrderedDict(gga='PS', pp='PBE'),
                   # Meta-GGAs
                   'tpss': OrderedDict(pp='PBE', metagga='TPSS'),
                   'revtpss': OrderedDict(pp='PBE', metagga='RTPSS'),
                   'm06l': OrderedDict(pp='PBE', metagga='M06L'),
                   # vdW-DFs
                   'optpbe_vdw': OrderedDict(pp='LDA', gga='OR', luse_vdw=True,
                                             aggac=0.0),
                   'optb88_vdw': OrderedDict(pp='LDA', gga='BO', luse_vdw=True,
                                             aggac=0.0, param1=1.1 / 6.0,
                                             param2=0.22),
                   'optb86b_vdw': OrderedDict(pp='LDA', gga='MK',
                                              luse_vdw=True, aggac=0.0,
                                              param1=0.1234, param2=1.0),
                   'vdw_df2': OrderedDict(pp='LDA', gga='ML', luse_vdw=True,
                                          aggac=0.0, zab_vdw=-1.8867),
                   'beef_vdw': OrderedDict(pp='PBE', gga='BF', luse_vdw=True,
                                           zab_vdw=-1.8867, lbeefens=True),
                   # hybrids
                   'pbe0': OrderedDict(pp='LDA', gga='PE', lhfcalc=True),
                   'hse03': OrderedDict(pp='LDA', gga='PE', lhfcalc=True,
                                        hfscreen=0.3),
                   'hse06': OrderedDict(pp='LDA', gga='PE', lhfcalc=True,
                                        hfscreen=0.2),
                   'b3lyp': OrderedDict(pp='LDA', gga='B3', lhfcalc=True,
                                        aexx=0.2, aggax=0.72, aggac=0.81,
                                        aldac=0.19),
                   'hf': OrderedDict(pp='PBE', lhfcalc=True, aexx=1.0,
                                     aldac=0.0, aggac=0.0)}
    return xc_settings[xc]


def gas_settings():
    ''' The default settings we use to do DFT calculations of gases '''
    gas_settings = OrderedDict(vasp=OrderedDict(ibrion=2,
                                                nsw=100,
                                                isif=0,
                                                kpts=(1, 1, 1),
                                                ediffg=-0.03,
                                                encut=350.,
                                                pp_version=pp_version(),
                                                **xc_settings(),
                                                **logfile_settings()))
    return gas_settings


def bulk_settings():
    ''' The default settings we use to do DFT calculations of bulks '''
    bulk_settings = OrderedDict(max_atoms=80,
                                vasp=OrderedDict(ibrion=1,
                                                 nsw=100,
                                                 isif=7,
                                                 isym=0,
                                                 ediff=1e-8,
                                                 kpts=(10, 10, 10),
                                                 prec='Accurate',
                                                 encut=500.,
                                                 pp_version=pp_version(),
                                                 **xc_settings(),
                                                 **logfile_settings()))
    return bulk_settings


def surface_energy_bulk_settings():
    '''
    The default settings we use to do DFT calculations of bulks
    spefically for surface energy calculations.
    '''
    SE_bulk_settings = OrderedDict(max_atoms=80,
                                   vasp=OrderedDict(ibrion=1,
                                                    nsw=100,
                                                    isif=7,
                                                    isym=0,
                                                    ediff=1e-8,
                                                    kpts=(10, 10, 10),
                                                    prec='Accurate',
                                                    encut=500.,
                                                    pp_version=pp_version(),
                                                    **xc_settings('pbesol'),
                                                    **logfile_settings()))
    return SE_bulk_settings


def slab_settings():
    '''
    The default settings we use to enumerate slabs, along with the subsequent
    DFT settings. The 'slab_generator_settings' are passed to the
    `SlabGenerator` class in pymatgen, and the `get_slab_settings` are passed
    to the `get_slab` method of that class.
    '''
    slab_settings = OrderedDict(max_miller=2,
                                max_atoms=80,
                                vasp=OrderedDict(ibrion=2,
                                                 nsw=100,
                                                 isif=0,
                                                 isym=0,
                                                 kpts=(4, 4, 1),
                                                 lreal='Auto',
                                                 ediffg=-0.03,
                                                 encut=350.,
                                                 pp_version=pp_version(),
                                                 **xc_settings('pbesol'),
                                                 **logfile_settings()),
                                slab_generator_settings=OrderedDict(min_slab_size=7.,
                                                                    min_vacuum_size=20.,
                                                                    lll_reduce=False,
                                                                    center_slab=True,
                                                                    primitive=True,
                                                                    max_normal_search=1),
                                get_slab_settings=OrderedDict(tol=0.3,
                                                              bonds=None,
                                                              max_broken_bonds=0,
                                                              symmetrize=False))
    return slab_settings


def adslab_settings():
    '''
    The default settings we use to enumerate adslab structures, along with the
    subsequent DFT settings. `mix_xy` is the minimum with of the slab
    (Angstroms) before we enumerate adsorption sites on it.
    '''
    adslab_settings = OrderedDict(min_xy=4.5,
                                  rotation=OrderedDict(
                                      phi=0., theta=0., psi=0.),
                                  vasp=OrderedDict(ibrion=2,
                                                   nsw=200,
                                                   isif=0,
                                                   isym=0,
                                                   kpts=(4, 4, 1),
                                                   lreal='Auto',
                                                   ediffg=-0.03,
                                                   symprec=1e-10,
                                                   encut=350.,
                                                   pp_version=pp_version(),
                                                   **xc_settings(),
                                                   **logfile_settings()))
    return adslab_settings


def adsorbates():
    '''
    A dictionary whose keys are the simple string names of adsorbates and whos
    values are their corresponding `ase.Atoms` objects. When making new entries
    for this dictionary, we recommend "pointing" the adsorbate upwards in the
    z-direction.
    '''
    adsorbates = {}
    adsorbates[''] = Atoms()

    # Uranium is a place-holder for an adsorbate
    adsorbates['U'] = Atoms('U')

    # We put some of these adsorbates closer to the slab to help them adsorb
    # onto the surface
    adsorbates['H'] = Atoms('H', positions=[[0., 0., -0.5]])


    adsorbates['N'] = Atoms('N', positions=[[0., 0., -1.]])
    adsorbates['O'] = Atoms('O')
    adsorbates['C'] = Atoms('C')

    "AVERAGE BOND 1.165"
    adsorbates['CO'] = Atoms('CO', positions=[[0., 0., 0.],
                                              [0., 0., 1.148]])




    # MS build adn vasp calc
    #adsorbates['CO2'] = Atoms(symbols=['C','O','O'], positions=[[0., 0., 0.],
    #                                                           [1.177, 0., 0],
    #                                                           [-1.177, 0, 0]])

    #Ti slab_001 OPT(ZUIZAO)
    adsorbates['CO2_1'] = Atoms(symbols=['C','O','O'], positions=[[0., 0., 0.],
                                                               [0.59250299,1.02608547,0.29225999],
                                                               [-0.59241074,-1.02608544,0.29194591]])
    #V slab_011 OPT(houlai)
    adsorbates['CO2'] = Atoms(symbols=['C','O','O'], positions=[[0., 0., 0.],
                                                               [1.10510335,-0.80439089,0.18423197],
                                                               [-1.22583122,-0.60635389,0.22554259]])
    

    # MS build and vasp calc
#    adsorbates['COOH'] = Atoms(symbols=['C','O','O','H'], positions=[[0., 0., 0.],
#                                                                     [-0.707, 0.808, 0.808],
#                                                                     [1.184, -0.134, -0.134],
#                                                                     [-0.073, 1.35,1.35]])
#
    # Al COOH slab_001 OPT
    adsorbates['COOH'] = Atoms(symbols=['C','H','O','O'], positions=[[0., 0., 0.],
                                                                     [0.08539948,0.11527301,1.90204107],
                                                                     [-0.60576478,0.07895150,1.19815674],
                                                                     [1.29133575,-0.01376527,0.01753967]])
    

     # MS build and vasp calc
    #adsorbates['HCOO'] = Atoms(symbols=['C','H','O','O'], positions=[[0., 0., 0.],
    #                                                                 [-0.557,-0.682, -0.682],
    #                                                                 [-0.566, 0.805, 0.805],
    #                                                                 [1.269, 0.056,0.056]])

    # Sn HCOO slab_001 OPT
    adsorbates['HCOO'] = Atoms(symbols=['O','O','H','C'], positions=[[0., 0., 0.],
                                                                     [-1.28744151,-0.11580243,1.85385915],
                                                                     [-2.03986964,-0.39016577,-0.02794676],
                                                                     [-1.16506837,-0.17617949,0.63972599]])

    # Ni_slab_001_HCOO_bridge1
    adsorbates['HCOO_bridge'] = Atoms(symbols=['O','O','H','C'], positions=[[0., 0., 0.0],
                                                                     [-0.47151650,0.11389140,2.22092136],
                                                                     [-1.93469193,-0.05542301,0.78188290],
                                                                     [-0.85602179,0.02151939,1.07467679]])

    # Al HCOO slab_111 OPT
    #adsorbates['HCOO'] = Atoms(symbols=['O','O','H','C'], positions=[[0., 0., 0.],
    #                                                                 [-1.13072035,1.98749627,0.00916715],
    #                                                                 [-0.51153205,1.01716509,1.68292964],
    #                                                                 [-0.54716437,1.00148109,0.57785997]])

    #MS dajian and vasp opt  c_terminate
    #adsorbates['HCOOH'] = Atoms(symbols=['C','H','H','O','O'], positions=[[0., 0., 0.],
    #                                                                 [-0.703,-0.61, -0.61],
    #                                                                 [-0.071, 1.341, 1.341],
    #                                                                 [-0.724, 0.822,0.822],
    #                                                                 [1.211,-0.054, -0.054]])
    #MS dajian and vasp opt  o_terminate
   # adsorbates['HCOOH'] = Atoms(symbols=['O','O','H','H','C'], positions=[[0., 0., 0.],
   #                                                                  [-1.93313348,0.87445518,0.87445520],
   #                                                                  [-1.28451730,1.39529189,1.39529194],
   #                                                                  [-1.91167291,-0.55369418,-0.55369414],
   #                                                                  [-1.21421637,0.05432444,0.05432446]])

    #MS dajian2
  #  adsorbates['HCOOH'] = Atoms(symbols=['O','O','H','H','C'], positions=[[0., 0., 0.],
  #                                                                   [-2.06702922,0.32547831,0.94247971],
  #                                                                   [-0.33824904,0.55017242,1.96240784],
  #                                                                   [-2.35272886,0.08525260,0.03473757],
  #                                                                   [-0.70307463,0.28406014,0.95159009]])

    #MS dajian2 and vasp opt by al_slab_001_hcooh,zaoqituijian
    adsorbates['HCOOH_1'] = Atoms(symbols=['O','O','H','H','C'], positions=[[0., 0., 0.],
                                                                     [-0.98445266,1.86873934,0.89084003],
                                                                     [-0.85087110,2.25841593,-0.05073748],
                                                                     [-0.52887592,0.22193275,1.95839871],
                                                                     [-0.48478260,0.65699687,0.94571982]])
    # Ga_111_opt houqituijian(af first opt)
    adsorbates['HCOOH'] = Atoms(symbols=['O','O','H','H','C'], positions=[[0., 0., 0.],
                                                                     [1.24305276,1.68125215,1.10466022],
                                                                     [-0.55237422,1.02228632,1.72323446],
                                                                     [1.72616015,1.92786370,0.28815654],
                                                                     [-0.03215103,1.18574061,0.76281079]])
    "my addition end"
    # For diatomics (and above), it's a good practice to manually relax the gases
    # and then see how far apart they are. Then put first atom at the origin, and
    # put the second atom directly above it.
    #adsorbates['CO'] = Atoms('CO', positions=[[0., 0., 0.],
    #                                          [0., 0., 1.2]])
    #adsorbates['OH'] = Atoms('OH', positions=[[0., 0., 0.],
    #                                          [0.92, 0., 0.32]])

    ## For OOH, we've found that most of our relaxations resulted in dissociation of
    ## at least the hydrogen. As such, we put some Hookean springs between the atoms
    ## to keep the adsorbate together.
    #adsorbates['OOH'] = Atoms('OOH', positions=[[0., 0., 0.],
    #                                            [1.28, 0., 0.67],
    #                                            [1.44, -0.96, 0.81]])
    #adsorbates['OOH'].set_constraint([ase.constraints.Hookean(a1=0, a2=1, rt=1.6, k=10.),   # Bind OO
    #                                  ase.constraints.Hookean(a1=1, a2=2, rt=1.37, k=5.)])  # Bind OH

    ## For CHO, assumed C binds to surface (index 0), O (index 1), and H(index 2).
    ## Trying to apply Hookean so that CH bound doesn't dissociate. Actual structure
    ## is H-C-O
   ## adsorbates['CHO'] = Atoms('CHO', positions=[[0., 0., 1.],
   ##                                             # position of H
   ##                                             [-0.94, 0.2, 1.7],
   ##                                             [0.986, 0.6, 1.8]])     # position of O

    #adsorbates['CHO'] = Atoms('CHO', positions=[[0., 0., 0.],
    #                                            # position of H
    #                                            [-0.94, 0.2, 0.7],
    #                                            [0.986, 0.6, 0.8]])     # position of O


    #adsorbates['CHO'].set_constraint([ase.constraints.Hookean(a1=0, a2=1, rt=1.59, k=5.),   # Bind CH, initially used k=7, lowered to 5
    #                                  ase.constraints.Hookean(a1=0, a2=2, rt=1.79, k=5.)])  # Bind CO

    return adsorbates


def adsorption_projection():
    '''
    WARNING:  A lot of code depends on this. Do not add or remove anything out
    without thinking very hard about it. If you do add something, consider
    changing the ignore_keys in `gaspy.gasdb.get_unsimulated_catalog_docs`.

    Returns:
        projection  A dictionary that is meant to be passed as a projection
                    operator to a Mongo `find` or `aggregate` command. The keys
                    here are the keys for the new dictionary/doc you are
                    making, and the values are where you can find the
                    information from the old Mongo docs (in our `adsorption`
                    collection).
    '''
    fingerprints = {'_id': 0,
                    'mongo_id': '$_id',
                    'adsorbate': '$adsorbate',
                    'mpid': '$mpid',
                    'miller': '$miller',
                    'shift': '$shift',
                    'top': '$top',
                    'coordination': '$fp_final.coordination',
                    'neighborcoord': '$fp_final.neighborcoord',
                    'energy': '$adsorption_energy'}
    return fingerprints


def adsorption_filters(adsorbate=None):
    '''
    Not all of our adsorption calculations are "good" ones. Some end up in
    desorptions, dissociations, do not converge, or have ridiculous energies.
    These are the filters we use to sift out these "bad" documents. It also
    happens to be the `query` operator we can pass to Mongo's `find` or
    `aggregate` commands.

    Arg:
        adsorbate   A string of the adsorbate that you want to get
                    calculations for.
    Returns:
        filters     A dictionary that is meant to be used as a `query` argument
                    for our `adsorption` Mongo collection's `find` or
                    `aggregate` commands.
    '''
    filters = {}

    # Easy-to-read (and change) filters before we distribute them
    # into harder-to-read (but mongo-readable) structures
    f_max = 0.5                 # Maximum atomic force [eV/Ang]
    ads_move_max = 1.5          # Maximum distance the adsorbate can move [Ang]
    # Maximum distance that any atom can move on bare slab [Ang]
    bare_slab_move_max = 0.5
    # Maximum distance that any slab atom can move after adsorption [Ang]
    slab_move_max = 1.5
    if adsorbate == 'CO':
        energy_range = (-7., 5.)
    elif adsorbate == 'H':
        energy_range = (-5., 5.)
    elif adsorbate == 'O':
        energy_range = (-4., 9.)
    elif adsorbate == 'OH':
        energy_range = (-3.5, 4.)
    elif adsorbate == 'OOH':
        energy_range = (0., 9.)
        ads_move_max = 4.5
    elif adsorbate == 'N':
        # We're going to be more lenient with nitrogen movement because it
        # tends to adsorb closely to the surface, but we don't want to put it
        # too close to the surface
        ads_move_max = 3.
        energy_range = (-5, 5)
    else:
        energy_range = (-50., 50.)
        warnings.warn('You are using adsorption document filters for an '
                      'adsorbate (%s) that we have not yet established valid '
                      'energy bounds for. We are accepting anything in the'
                      'range between %i and %i eV.'
                      % (adsorbate, energy_range[0], energy_range[1]),
                      UserWarning)

    # Distribute filters into mongo-readable form
    filters['adsorption_energy'] = {
        '$gt': energy_range[0], '$lt': energy_range[1]}
    filters['results.fmax'] = {'$lt': f_max}
    filters['movement_data.max_adsorbate_movement'] = {'$lt': ads_move_max}
    filters['movement_data.max_bare_slab_movement'] = {
        '$lt': bare_slab_move_max}
    filters['movement_data.max_slab_movement'] = {'$lt': slab_move_max}
    filters['vasp_settings.gga'] = xc_settings()['gga']

    return filters


def surface_projection():
    '''
    WARNING:  A lot of code depends on this. Do not take anything out without
    thinking very hard about it.

    Returns:
        projection  A dictionary that is meant to be passed as a projection
                    operator to a Mongo `find` or `aggregate` command. The keys
                    here are the keys for the new dictionary/doc you are
                    making, and the values are where you can find the
                    information from the old Mongo docs (in our
                    `surface_energy` collection).
    '''
    fingerprints = {'_id': 0,
                    'mongo_id': '$_id',
                    'mpid': '$mpid',
                    'miller': '$miller',
                    'shift': '$shift',
                    'intercept': '$surface_energy',
                    'intercept_uncertainty': '$surface_energy_standard_error',
                    'thinnest_structure': {'$arrayElemAt': ['$surface_structures', 0]},
                    'FW_info': '$fwids'}
    return fingerprints


def surface_filters():
    '''
    Not all of our surface energy calculations are "good" ones. Some do not
    converge or have end up having a lot of movement. These are the filters we
    use to sift out these "bad" documents. It also happens to be the `query`
    operator we can pass to Mongo's `find` or `aggregate` commands.

    Returns:
        filters     A dictionary that is meant to be used as a `query` argument
                    for our `surface_energy` Mongo collection's `find` or
                    `aggregate` commands.
    '''
    filters = {}

    # Easy-to-read (and change) filters before we distribute them
    # into harder-to-read (but mongo-readable) structures
    f_max = 0.5                 # Maximum atomic force [eV/Ang]
    max_surface_movement = 1.   # Maximum distance that any atom can move [Ang]

    # Distribute filters into mongo-readable form
    filters['surface_structures.0.results.fmax'] = {'$lt': f_max}
    filters['surface_structures.1.results.fmax'] = {'$lt': f_max}
    filters['surface_structures.2.results.fmax'] = {'$lt': f_max}
    filters['max_atom_movement.0'] = {'$lt': max_surface_movement}
    filters['max_atom_movement.1'] = {'$lt': max_surface_movement}
    filters['max_atom_movement.2'] = {'$lt': max_surface_movement}
    filters['vasp_settings.gga'] = xc_settings('pbesol')['gga']

    return filters


def catalog_projection():
    '''
    WARNING:  A lot of code depends on this. Do not add or remove anything out
    without thinking very hard about it. If you do add something, consider
    changing the ignore_keys in `gaspy.gasdb.get_unsimulated_catalog_docs`.

    Returns:
        projection  A dictionary that is meant to be passed as a projection
                    operator to a Mongo `find` or `aggregate` command. The keys
                    here are the keys for the new dictionary/doc you are
                    making, and the values are where you can find the
                    information from the old Mongo docs (in our `catalog`
                    collection).
    '''
    projection = {'_id': 0,
                  'mongo_id': '$_id',
                  'mpid': '$mpid',
                  'miller': '$miller',
                  'shift': '$shift',
                  'top': '$top',
                  'natoms': '$atoms.natoms',
                  'coordination': '$coordination',
                  'neighborcoord': '$neighborcoord',
                  'adsorption_site': '$adsorption_site'}
    return projection


def model():
    '''
    We use surrogate models to make predictions of DFT information. This is the
    tag associated with our default model.
    '''
    return 'model0'
