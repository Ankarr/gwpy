# Licensed under a 3-clause BSD style license - see LICENSE.rst

"""This module provides an extension to the :class:`numpy.ndarray`
data structure providing metadata

The `Array` structure provides the core array-with-metadata environment
with the standard array methods wrapped to return instances of itself.
"""

import numpy

from astropy.units import (Unit, Quantity)
from astropy.io import registry

from ..detector import Channel
from ..time import Time

from ..version import version as __version__
__author__ = "Duncan Macleod <duncan.macleod@ligo.org>"
__credits__ = "Nickolas Fotopoulos <nvf@gravity.phys.uwm.edu>"


# -----------------------------------------------------------------------------
# Core Array

class Array(numpy.ndarray):
    """An extension of the :class:`~numpy.ndarray`, with added
    metadata

    This `Array` holds the input data and a standard set of metadata
    properties associated with GW data.

    Parameters
    ----------
    data : array-like, optional, default: `None`
        input data array
    dtype : :class:`~numpy.dtype`, optional, default: `None`
        input data type
    copy : `bool`, optional, default: `False`
        choose to copy the input data to new memory
    subok : `bool`, optional, default: `True`
        allow passing of sub-classes by the array generator
    **metadata
        other metadata properties

    Returns
    -------
    array : `Array`
        a new array, with a view of the data, and all associated metadata

    Attributes
    ----------
    name
    unit
    """
    __array_priority_ = 10.1
    _metadata_type = dict
    _metadata_slots = ['name', 'unit']

    def __new__(cls, data=None, dtype=None, copy=False, subok=True,
                **metadata):
        """Define a new `Array`, potentially from an existing one
        """
        # copy from an existing Array
        if isinstance(data, cls):
            if dtype is None:
                dtype = data.dtype
            else:
                dtype = numpy.dtype(dtype)
            if not copy and dtype == data.dtype and not metadata:
                return data
            elif metadata:
                new = numpy.array(data, dtype=dtype, copy=copy, subok=True)
                new.metadata = cls._metadata_type(metadata)
                return new
            else:
                new = data.astype(dtype)
                new.metadata = data.metadata
                return new
        # otherwise define a new Array from the array-like data
        else:
            new = numpy.array(data, dtype=dtype, copy=copy, subok=True)
            _baseclass = type(new)
            new = new.view(cls)
            new.metadata = cls._metadata_type()
            for key,val in metadata.iteritems():
                if val is not None:
                    setattr(new, key, val)
            new._baseclass = _baseclass
            return new

    # -------------------------------------------
    # array manipulations

    def __array_finalize__(self, obj):
        """Finalize a Array with metadata
        """
        self.metadata = getattr(obj, 'metadata', None)
        self._baseclass = getattr(obj, '_baseclass', type(obj))

    def __array_wrap__(self, obj, context=None):
        """Wrap an array as a Array with metadata
        """
        result = obj.view(self.__class__)
        result.metadata = self.metadata.copy()
        try:
            ufunc = context[0]
            args = [isinstance(arg, self.__class__) and arg.unit or arg for
                    arg in context[1]]
            result.unit = ufunc(*args)
        except TypeError:
            pass
        return result

    def __repr__(self):
        indent = ' '*len('<%s(' % self.__class__.__name__)
        array = repr(self.view(numpy.ndarray))[6:-1].replace(' '*6, indent)
        metadata = ('\n%s' % indent).join(
                       ['%s=%s' % (key,self.metadata[key]) for
                        key in self._metadata_slots if
                        self.metadata.has_key(key)])
        return "<%s(%s\n%s%s)>" % (self.__class__.__name__, array,
                                   indent, metadata)

    def __str__(self):
        indent = ' '*len('%s(' % self.__class__.__name__)
        array = repr(self.view(numpy.ndarray))[6:-1].replace(' '*6, indent)
        metadata = (',\n%s' % indent).join(
                       ['%s=%s' % (key,val) for
                        key,val in self.metadata.iteritems() if key != 'index'])
        return "%s(%s,\n%s%s)>" % (self.__class__.__name__, array,
                                    indent, metadata)

    # -------------------------------------------
    # array methods

    def median(self, axis=None, out=None, overwrite_input=False):
        return numpy.median(self, axis=axis, out=out,
                            overwrite_input=overwrite_input)
    median.__doc__ = numpy.median.__doc__

    @property
    def T(self):
        return self.transpose()

    @property
    def H(self):
        return self.T.conj()

    @property
    def data(self):
        return self.view(numpy.ndarray)
    A = data

    # -------------------------------------------
    # Pickle helpers

    def __getstate__(self):
        """Return the internal state of the object
        """
        state = (1,
                 self.shape,
                 self.dtype,
                 self.flags.fnc,
                 self.A.tostring(),
                 self.metadata.todict(),
                 )
        return state

    def __setstate__(self, state):
        """Restore the internal state of the masked array

        This is used for unpickling purposes.

        Parameters
        ----------
        state : `tuple`
            typically the output of the :meth:`Array.__get__state`
            method, aa 5-tuple containing:

            - class name
            - a tuple giving the shape of the data
            - a typecode for the data
            - a binary string for the data
            - a binary string for the mask.
        """
        (ver, shp, typ, isf, raw, meta) = state
        if ver != 1:
            raise NotImplementedError
        numpy.ndarray.__setstate__(self, (shp, typ, isf, raw))
        self.metadata = self._metadata_type(meta)

    def __reduce__(self):
        """Return a 3-tuple for pickling a `Array`:
            - reconstruction function
            - tuple to pass reconstruction function
            - state, which will be passed to __setstate__
        """
        return (_mareconstruct,
                (self.__class__, self._baseclass, (0,), 'b', ),
                self.__getstate__())

    # -------------------------------------------
    # Array properties

    @property
    def name(self):
        """Name for this `Array`

        :type: `str`
        """
        return self.metadata['name']

    @name.setter
    def name(self, val):
        self.metadata['name'] = str(val)

    @property
    def unit(self):
        """Unit for this `Array`

        :type: :class:`~astropy.units.Unit`
        """
        try:
            return self.metadata['unit']
        except KeyError:
            self.unit = ''
            return self.unit

    @unit.setter
    def unit(self, val):
        if val is None or isinstance(val, Unit):
            self.metadata['unit'] = val
        else:
            self.metadata['unit'] = Unit(val)

    # -------------------------------------------
    # extras

    @classmethod
    def _getAttributeNames(cls):
        return cls._metadata_slots

    read = classmethod(registry.read)
    write = registry.write