# cython: profile=False
"""
Marking function definitions that take the 3D position of each point as an argument
"""

from __future__ import absolute_import, division, print_function, unicode_literals
import numpy as np
cimport numpy as cnp
from libc.math cimport fabs as c_fabs
from libc.math cimport sqrt as c_sqrt
from libc.math cimport cos as c_cos
from libc.math cimport acos as c_acos
from libc.math cimport sin as c_sin

__author__ = ["Duncan Campbell"]


cdef cnp.float64_t gamma_plus_func(cnp.float64_t* w1, cnp.float64_t* w2,
            cnp.float64_t x1, cnp.float64_t y1,
            cnp.float64_t x2, cnp.float64_t y2, cnp.float64_t dxy_sq):
    """
    """
    cdef cnp.float64_t x, y
    cdef cnp.float64_t costheta, gamma
    
    if dxy_sq>0:
        x = (x2-x1)
        y = (y2-y1)
        costheta = (w1[0]*x + w1[1]*y)/c_sqrt(dxy_sq)
        if costheta >= 1.0:
            return 0
        elif costheta <= -1.0:
            return w1[2]
        else:
            gamma = c_cos(2.0*c_acos(costheta))
            return w1[2]*w2[2]*gamma
    else:
        return 0.0

cdef cnp.float64_t gamma_cross_func(cnp.float64_t* w1, cnp.float64_t* w2,
            cnp.float64_t x1, cnp.float64_t y1,
            cnp.float64_t x2, cnp.float64_t y2, cnp.float64_t dxy_sq):
    """
    """
    cdef cnp.float64_t x, y
    cdef cnp.float64_t costheta, gamma
    
    if dxy_sq>0:
        x = (x2-x1)
        y = (y2-y1)
        costheta = (w1[0]*x + w1[1]*y)/c_sqrt(dxy_sq)
        gamma = c_sin(2.0*c_acos(costheta))
        return w1[2]*w2[2]*gamma
    else:
        return 0.0



