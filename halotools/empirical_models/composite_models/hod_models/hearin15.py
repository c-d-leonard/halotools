# -*- coding: utf-8 -*-
"""

Module containing some commonly used composite HOD models.

"""
from __future__ import (
    division, print_function, absolute_import, unicode_literals)

import numpy as np

from ... import factories, model_defaults
from ...occupation_models import leauthaud11_components 

from ...phase_space_models import NFWPhaseSpace, TrivialPhaseSpace

from ....sim_manager import FakeSim, sim_defaults


__all__ = ['Hearin15']


def Hearin15(central_assembias_strength = 1, 
    central_assembias_strength_abcissa = [1e12], 
    satellite_assembias_strength = 0.2, 
    satellite_assembias_strength_abcissa = [1e12], 
    **kwargs):
    """ 
    HOD-style model in which central and satellite occupations statistics are assembly-biased. 

    Parameters 
    ----------
    threshold : float, optional
        Stellar mass threshold of the mock galaxy sample. 
        Default value is specified in the `~halotools.empirical_models.model_defaults` module.

    sec_haloprop_key : string, optional  
        String giving the column name of the secondary halo property modulating 
        the occupation statistics of the galaxies. 
        Default value is specified in the `~halotools.empirical_models.model_defaults` module.

    central_assembias_strength : float or list, optional 
        Fraction or list of fractions between -1 and 1 defining 
        the assembly bias correlation strength. Default is a constant strength of 0.5. 

    central_assembias_strength_abcissa : list, optional 
        Values of the primary halo property at which the assembly bias strength is specified. 
        Default is a constant strength of 0.5. 

    satellite_assembias_strength : float or list, optional 
        Fraction or list of fractions between -1 and 1 defining 
        the assembly bias correlation strength. Default is a constant strength of 0.5. 

    satellite_assembias_strength_abcissa : list, optional 
        Values of the primary halo property at which the assembly bias strength is specified. 
        Default is a constant strength of 0.5. 

    split : float, optional 
        Fraction between 0 and 1 defining how 
        we split halos into two groupings based on 
        their conditional secondary percentiles. 
        Default is 0.5 for a constant 50/50 split. 

    redshift : float, optional  
        Default is set in the `~halotools.sim_manager.sim_defaults` module. 

    concentration_binning : tuple, optional 
        Three-element tuple. The first entry will be the minimum 
        value of the concentration in the lookup table for the satellite NFW profile, 
        the second entry the maximum, the third entry 
        the linear spacing of the grid. 
        Default is set in `~halotools.empirical_models.model_defaults`.  
        If high-precision is not required, the lookup tables will build much faster if 
        ``concentration_binning`` is set to (1, 25, 0.5).

    Examples 
    --------
    >>> model = Hearin15()

    To use our model to populate a simulation with mock galaxies, we only need to 
    load a snapshot into memory and call the built-in ``populate_mock`` method:

    >>> model.populate_mock() # doctest: +SKIP

    """     
    ##############################
    ### Build the occupation model
    if central_assembias_strength == 0:
        cen_ab_component = leauthaud11_components.Leauthaud11Cens(**kwargs)
    else:
        cen_ab_component = leauthaud11_components.AssembiasLeauthaud11Cens(
            assembias_strength = central_assembias_strength, 
            assembias_strength_abcissa = central_assembias_strength_abcissa, 
            **kwargs)
    subpopulation_blueprint_centrals = {}
    subpopulation_blueprint_centrals['occupation'] = cen_ab_component

    # Build the profile model
    profile_feature_centrals = TrivialPhaseSpace(**kwargs)
    subpopulation_blueprint_centrals['profile'] = profile_feature_centrals

    ##############################
    ### Build the occupation model
    if satellite_assembias_strength == 0:
        sat_ab_component = leauthaud11_components.Leauthaud11Sats(**kwargs)
    else:
        sat_ab_component = leauthaud11_components.AssembiasLeauthaud11Sats(
            assembias_strength = satellite_assembias_strength, 
            assembias_strength_abcissa = satellite_assembias_strength_abcissa, 
            **kwargs)
        # There is no need for a redundant new_haloprop_func_dict 
        # if this is already possessed by the central model
        if hasattr(cen_ab_component, 'new_haloprop_func_dict'):
            del sat_ab_component.new_haloprop_func_dict

    subpopulation_blueprint_satellites = {}
    subpopulation_blueprint_satellites['occupation'] = sat_ab_component

    # Build the profile model
    profile_feature_satellites = NFWPhaseSpace(**kwargs) 
    profile_feature_satellites._suppress_repeated_param_warning = True   
    subpopulation_blueprint_satellites['profile'] = profile_feature_satellites

    model_blueprint = {'centrals': subpopulation_blueprint_centrals, 'satellites': subpopulation_blueprint_satellites}
    composite_model = factories.HodModelFactory(model_blueprint)
    return composite_model
