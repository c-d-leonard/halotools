# -*- coding: utf-8 -*-
"""

This module contains the components for 
the intra-halo spatial positions of galaxies 
used by `halotools.hod_designer` to build composite HOD models 
by composing the behavior of the components. 

"""

from astropy.extern import six
from abc import ABCMeta, abstractmethod, abstractproperty

import numpy as np
from scipy.interpolate import UnivariateSpline as spline

from utils.array_utils import array_like_length as aph_len
import occupation_helpers as occuhelp 
import defaults

##################################################################################

class TrivialCenProfile(object):
    """ Profile assigning central galaxies to reside at exactly the halo center."""

    def __init__(self, gal_type):
        self.gal_type = gal_type

    def mc_coords(self, *args,**kwargs):

        too_many_args = (occuhelp.aph_len(args) > 0) & ('mock_galaxies' in kwargs.keys())
        if too_many_args == True:
            raise TypeError("TrivialCenProfile can be passed an array, or a mock, but not both")

        # If we are running in testmode, require that all galaxies 
        # passed to mc_coords are actually the same type
        runtest = ( (defaults.testmode == True) & 
            ('mock_galaxies' in kwargs.keys()) )
        if runtest == True:
            assert np.all(mock_galaxies.gal_type == self.gal_type)
        ###

        return 0

##################################################################################

class IsotropicSats(object):
    """ Classical satellite profile. """

    def __init__(self, gal_type):
        self.gal_type = gal_type

    def mc_angles(self,coords):
        """
        Generate a list of Ngals random points on the unit sphere. 
        The coords array is passed as input to save memory, 
        speeding up satellite position assignment when building mocks.

        """
        Ngals = aph_len(coords[:,0])
        cos_t = np.random.uniform(-1.,1.,Ngals)
        phi = np.random.uniform(0,2*np.pi,Ngals)
        sin_t = np.sqrt((1.-(cos_t*cos_t)))
        
        coords[:,0] = sin_t * np.cos(phi)
        coords[:,1] = sin_t * np.sin(phi)
        coords[:,2] = cos_t

        return coords

    def mc_coords(self,coords,inv_cumu_prof_func,system_center,host_Rvir):
        Ngals = aph_len(coords[:,0])
        random_cumu_prof_vals = np.random.random(Ngals)

        r_random = inv_cumu_prof_func(random_cumu_prof_vals)*host_Rvir

        coords *= r_random.reshape(Ngals,1)
        coords += system_center.reshape(1,3)

        return coords


##################################################################################
class RadProfBias(object):
    """ Conventional model for the spatial bias of satellite galaxies. 
    The profile parameters governing the satellite distribution are set to be 
    a scalar multiple of the profile parameters of their host halo. 

    Traditionally applied to the NFW case, where the only profile parameter is 
    halo concentration, and the scalar multiple is mass-independent. This 
    traditional model is a special case of this class, 
    which encompasses halo-dependent spatial bias, non-NFW profiles, 
    as well as (mass-dependent) quenching gradients. 
    """

    def __init__(self, gal_type, halo_prof_model, 
        input_prof_params=[], input_abcissa_dict={}, input_ordinates_dict={}, 
        interpol_method='spline',input_spline_degree=3):
        """ 
        Parameters 
        ----------
        gal_type : string, optional
            Sets the key value used by `halotools.hod_designer` and 
            `~halotools.profile_factory` to access the behavior of the methods 
            of this class. 

        halo_prof_model : object 
            `~halotools.HaloProfileModel` class instance. The primary function of this class 
            is to modulate the mean values of `~halotools.HaloProfileModel` as a function of 
            halo properties. 

        input_prof_params : array_like, optional
            string array specifying the halo profile parameters to be modulated. If passed, 
            input_abcissa_dict and input_ordinates_dict should not be passed, and 
            the abcissa and ordinates defining the modulation of the halo profile parameters 
            will be set according to the default_profile_dict dict in `~halotools.defaults`

        input_abcissa_dict : dictionary, optional 
            Dictionary whose keys are halo profile parameters and values 
            are the abcissa used to define the profile parameter modulating function. 
            Default values are set according to default_profile_dict in `~halotools.defaults`
            If passed, input_ordinates_dict must also be passed, 
            and the input_prof_params list may not.

        input_ordinates_dict : dictionary, optional 
            Dictionary whose keys are halo profile parameters and values 
            are the ordinates used to define the profile parameter modulating function. 
            Default values are set according to default_profile_dict in `~halotools.defaults`
            If passed, input_abcissa_dict must also be passed, 
            and the input_prof_params list may not.

        interpol_method : string, optional 
            Keyword specifying how `radprof_modfunc` 
            evaluates input values that differ from the small number of values 
            in self.parameter_dict. 
            The default spline option interpolates the model's abcissa and ordinates. 
            The polynomial option uses the unique, degree N polynomial 
            passing through the ordinates, where N is the number of supplied ordinates. 

        input_spline_degree : int, optional
            Degree of the spline interpolation for the case of interpol_method='spline'. 
            If there are k abcissa values specifying the model, input_spline_degree 
            is ensured to never exceed k-1, nor exceed 5. 

        """

        self.gal_type = gal_type
        self.halo_prof_model = halo_prof_model


        self.set_parameter_dict(input_prof_params,input_abcissa_dict,input_ordinates_dict)

        #self.input_abcissa_dict = input_abcissa_dict
        #self.input_ordinates_dict = input_ordinates_dict

        #self.abcissa_key = {}
        #self.ordinates_key = {}


        # Set the interpolation scheme 
        if interpol_method not in ['spline', 'polynomial']:
            raise IOError("Input interpol_method must be 'polynomial' or 'spline'.")
        self.interpol_method = interpol_method
        if self.interpol_method=='spline':
            self.input_spline_degree=input_spline_degree
            self._setup_spline()

    def get_modulated_prof_params(prof_param_keys, *args, **kwargs):
        """ 

        Parameters 
        ----------
        prof_param_keys : array_like

        input_params : array_like, optional positional argument

        mock_galaxies : object, optional keyword argument 

        Returns 
        ------- 
        output_param_dict : dict

        """

        input_param_dict = self.retrieve_input_prof_params(
            prof_param_keys, args, kwargs)

        output_param_dict = {}
        for prof_param_key in prof_param_keys:
            multiplicative_modulation = (
                self.radprof_modfunc(
                    prof_param_key, input_param_dict[prof_param_key])
                )
            output_param_dict[prof_param_key] = (
                multiplicative_modulation*input_param_dict[prof_param_key]
                )

        return output_param_dict


    def retrieve_input_prof_params(self, prof_param_keys, *args, **kwargs):
        """ Method to create a dictionary containing arrays of 
        input halo profile parameters that are to be modulated. 
        The keys of the output dictionary provide instructions to 
        the rest of the class about which model parameters to use 
        to modulate the input arrays. 

        Parameters 
        ----------
        prof_param_keys : array_like

        input_params : array_like, optional positional argument

        mock_galaxies : object, optional keyword argument 

        Returns 
        ------- 
        input_param_dict : dict

        """

        ###
        prof_param_keys = list(prof_param_keys)
        # First retrieve the profile parameters of the halos 
        if occuhelp.aph_len(args) > 0:
            # We were passed an array of profile parameters, 
            # so we should not have also been passed a galaxy sample
            if 'mock_galaxies' in kwargs.keys():
                raise TypeError("RadProfBias can be passed an array, "
                    "or a mock, but not both")
            input_param_dict = {prof_param_keys[ii]:value for ii, value in enumerate(args)}
        elif (occuhelp.aph_len(args) == 0) & ('mock_galaxies' in kwargs.keys()):
            # We were passed a collection of galaxies
            mock_galaxies = kwargs['mock_galaxies']
            input_param_dict = {key:getattr(mock_galaxies, key) for key in prof_param_keys}
        else:
            raise SyntaxError("get_modified_prof_params was called with "
                " incorrect inputs. Method accepts a positional argument that is an array "
                "storing the initial profile parameters to be modulated, "
                "or alternatively a mock galaxy object with the same array"
                " stored in the mock_galaxies.prof_param_keys attribute")

        return input_param_dict


    def radprof_modfunc(self,profile_parameter_key,input_abcissa):
        """
        Factor by which gal_type galaxies differ from are quiescent 
        as a function of the primary halo property.

        Parameters 
        ----------
        input_abcissa : array_like
            array of primary halo property 

        profile_parameter_key : string
            Dictionary key of the profile parameter being modulated, e.g., 'conc'. 

        Returns 
        -------
        output_profile_modulation : array_like
            Values of the profile parameters evaluated at input_abcissa. 

        Notes 
        -----
        Either assumes the profile parameters are modulated from those 
        of the underlying dark matter halo by a polynomial function 
        of the primary halo property, or is interpolated from a grid. 
        Either way, the behavior of this method is fully determined by 
        its values at the model abcissa, as specified in parameter_dict. 
        """

        model_abcissa, model_ordinates = (
            self.retrieve_model_abcissa_ordinates(profile_parameter_key)
            )

        if self.interpol_method=='polynomial':
            output_profile_modulation = occuhelp.polynomial_from_table(
                model_abcissa,model_ordinates,input_abcissa)
        elif self.interpol_method=='spline':
            modulating_function = self.spline_function[profile_parameter_key]
            output_profile_modulation = modulating_function(input_abcissa)
        else:
            raise IOError("Input interpol_method must be 'polynomial' or 'spline'.")

        return output_profile_modulation

    def retrieve_model_abcissa_ordinates(self, profile_parameter_key):
        """ Method to pack the values of the model parameters 
        into a list used by radprof_modfunc. 

        Parameters 
        ----------
        profile_parameter_key : string 
            Specifies the halo profile parameter to be modulated by the model.

        Returns 
        -------
        abcissa : array_like 
            Array at which the values of the modulating function are anchored. 

        ordinates : array_like
            Array of values of the modulating function when evaulated at the abcissa. 

        """

        abcissa = self.abcissa_dict[profile_parameter_key]

        # The initial ordinates can be accessed in the same way as the initial abcissa 
        # However, the ordinates may have changed from their initial values, 
        # for example by an MCMC walkers. So we must access the up-to-date ordinate values 
        # through self.parameter_dict, which is how the outside world modifies the 
        # model parameters. The keys to this dictionary are strings such as 
        # 'halo_NFW_conc_pari_gal_type', whose value is ordinates[i]. However, 
        # dictionaries have no intrinsic ordering, so in order to 
        # construct our ordinates list, we have to jump through a few hoops. 
        relevant_sub_dict = {}
        for key, value in self.parameter_dict.iteritems():
            if key[0:len(profile_parameter_key)]==profile_parameter_key:
                relevant_sub_dict[key] = value

        ordinates = []
        for ipar in range(len(relevant_sub_dict)):
            key_ipar = profile_parameter_key+'_biasfunc_par'+str(ipar+1)+self.gal_type
            value_ipar = relevant_sub_dict[key_ipar]
            ordinates.extend([value_ipar])

 
        return abcissa, ordinates


    def test_sensible_inputs(self, input_prof_params, input_abcissa_dict, input_ordinates_dict):

        if input_prof_params is not []:
            try:
                assert input_abcissa_dict is {}
            except:
                raise SyntaxError("If passing input_prof_params to the constructor,"
                    " do not pass input_abcissa_dict")
            try:
                assert input_ordinates_dict is {}
            except:
                raise SyntaxError("If passing input_prof_params to the constructor,"
                    " do not pass input_ordinates_dict")
            try:
                assert set(input_prof_params).issubset(
                    set(self.halo_prof_model.param_keys))
            except:
                raise SyntaxError("Entries of input_prof_params must be keys of halo_prof_model")
        else:
            try:
                assert input_abcissa_dict is not {}
            except:
                raise SyntaxError("If not passing input_prof_params to the constructor,"
                    "must pass input_abcissa_dict")
            try:
                assert input_ordinates_dict is not {}
            except:
                raise SyntaxError("If not passing input_ordinates_dict to the constructor,"
                    "must pass input_abcissa_dict")

    def set_parameter_dict(self, input_prof_params, input_abcissa_dict, input_ordinates_dict):
        """
        """

        self.test_sensible_inputs(input_prof_params, input_abcissa_dict, input_ordinates_dict)

        self.input_abcissa_dict={}
        self.input_ordinates_dict={}

        if input_prof_params is not []:
            for prof_param_key in input_prof_params:
                self.input_abcissa_dict[prof_param_key] = defaults.default_profile_dict['profile_abcissa']
                self.input_ordinates_dict[prof_param_key] = defaults.default_profile_dict['profile_ordinates']
        else:
            self.input_abcissa_dict[prof_param_key] = input_abcissa_dict
            self.input_ordinates_dict[prof_param_key] = input_ordinates_dict

        self.parameter_dict = 

        # For any parameter, the correct keys of its associate dictionary 
        # are strings for the abcissa and ordinate arrays
        # with a naming convention set in the defaults module
        correct_keys = defaults.default_profile_dict.keys()
        occuhelp.test_correct_keys(self.input_parameter_dict, correct_keys)
        # Now the keys of self.input_parameter_dict, and the keys of the 
        # sub-dictionaries, have been verified to be sensible
        ###

        if type(self.input_parameter_dict) is list:
            # Only a list of strings was provided specifying the profile bias, 
            # so choose the default abcissa and ordinates to define the model behavior
            default_value = defaults.default_profile_dict
            self.parameter_dict = (
                [{key:default_value} for key in self.input_parameter_dict]
                )
        elif type(self.input_parameter_dict) is dict:
            # Here the abcissa and ordinates were passed to the constructor. 
            self.parameter_dict = self.input_parameter_dict
        else:
            raise TypeError("input_parameter_dict must be a dict or a list")

        # Now use a dictionary comprehension to rename the keys 
        # so that abcissa & ordinates pertaining to different 
        # profile parameters have distinct keynames
        for key, dict_of_key in self.input_parameter_dict.iteritems():
            new_dict_of_key = ({key+'_biasfunc_par'+str(ii)+'_'+self.gal_type:val 
                for ii, val in enumerate(dict_of_key['profile_ordinates'])}
                )



        # Loop over all profile parameters that are being modulated 
        for profile_parameter, parameter_dict in self.parameter_dict.iteritems():
            # Append the table_dictionary of each profile parameter 
            # to self.parameter_dict 
#            new_dict_to_append = occuhelp.format_parameter_keys(parameter_dict,
#                correct_keys, self.gal_type, key_prefix=profile_parameter)
#            self.parameter_dict = dict(
#                self.parameter_dict.items() + 
#                new_dict_to_append.items() 
#                )
            # The radprof_modfunc method needs to access the ordinates and abcissa
            # This is accomplished by binding the key to an attribute of the model object
            # This binding is done via a dictionary, where each key of the dictionary 
            # corresponds to a profile parameter that is being modulated.
            self.abcissa_key[profile_parameter] = (
                profile_parameter+'_model_abcissa_'+self.gal_type )
            self.ordinates_key[profile_parameter] = (
                profile_parameter+'_model_ordinates_'+self.gal_type )



    def _setup_spline(self):
        # If using spline interpolation, configure its settings 
        
        scipy_maxdegree = 5
        self.spline_degree ={}
        self.spline_function = {}

        for profile_parameter, profile_parameter_dict in self.input_parameter_dict.iteritems():
            self.spline_degree[profile_parameter] = (
                np.min(
            [scipy_maxdegree, self.input_spline_degree, 
            aph_len(self.parameter_dict[self.abcissa_key[profile_parameter]])-1])
                )
            self.spline_function[profile_parameter] = occuhelp.aph_spline(
                self.parameter_dict[self.abcissa_key[profile_parameter]],
                self.parameter_dict[self.ordinates_key[profile_parameter]],
                k=self.spline_degree[profile_parameter])

















        







