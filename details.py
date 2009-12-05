import re

class MalformedPlaneFormat(Exception):
    pass

class PixelPlaneFormat(tuple):
    '''PixelFormat describes the layout of one plane of pixel data. See PixelFormat for                         
       details.
    '''
    
    _layput_pattern1 = re.compile(r"(?:[a-zA-Z]\d+)+")
    _find_pattern1 = re.compile(r"([a-zA-Z])(\d+)")

    _layput_pattern2 = re.compile(r"([a-zA-Z]+)(\d+)")

    def __new__(cls, plane_description):
        '''A plane descriptions is a tuple (n, layout, (x-divisor, y-divisor))
           where n is the number of pixels described (the pixel_span, usually one or two)
           layout is a string that describes the dstribution of channel bits inside n pixels
           x-divisor and y-divisor are horizontal and vertical subsampling factors.
           if n is one, it can be omitted
           if subsampling is (1,1) it can be omitted, too.
        '''

        t = cls._parse_plane(plane_description)
        if t is None:
            raise MalformedPlaneFormat()
        return tuple.__new__(cls, t)

    def _get_bits_per_sample(self):
        '''return number of bits per sample in this plane.'''
        plane_total = 0.0
        n, layout, subsampling = self
        for channel, fractions in layout:
            for start, width in fractions:
                plane_total += width
        return plane_total

    @classmethod
    def _parse_plane(cls, x):
        if type(x) == cls:
            return x
        t = None
        if type(x) == str:
            t = (1, x, (1,1))
        elif type(x) == tuple:
            if len(x) == 3:
                t = x
            if len(x) == 2:
                if (type(x[0])==str or type(x[0])==tuple) and type(x[1])==tuple:
                    t = (1,) + x
                elif type(x[0]) == int and (type(x[1]) == str or type(x[1])==tuple):
                    t = x + ((1,1),)
        
        if t is None: return None
        n, layout, subsampling = t
        if not type(n) == int or not type(subsampling) == tuple or not len(subsampling)==2:
            return None
        channels = cls._parse_layout(layout)
        if channels is not None:
            return (n, channels, subsampling)
        return None

    @classmethod
    def _parse_layout(cls, s):
        if type(s) == tuple:
            return s
        if type(s) != str:
            return None
        if cls._layput_pattern1.match(s):
            channels = cls._find_pattern1.findall(s)
        else:
            m = cls._layput_pattern2.match(s)
            if m:
                names, widths = m.groups()
                if len(names) != len(widths):
                    raise MalformedPlaneFormat()
                channels = zip(names, widths)
            else:
                raise MalformedPlaneFormat()
        
        pos = 0
        d = {}
        for name, width in channels:
            width = int(width)
            if not name in d.keys():
                d [name] = [(pos, width)]
            else:
                d[name].append((pos, width))
                
            pos += width
        for k,v in d.items(): d[k]=tuple(v)
        return tuple(d.items())


class PixelFormat(tuple):
    '''PixelFormat describes the layout of one or more planes of pixel data'''
    
    # The tuples and names below can be considered
    # examples of different forms of valied PixelFormat descriptors that can be
    # passed to PixelFormat.__new__
    _named_formats = {
        'yuv420p': ('y8', ('u8', (2,2)), ('v8', (2,2))),
        'yuv422p': ('y8', ('u8', (2,1)), ('v8', (2,1))),
        'uyvy'   : (2, 'u8y8v8y8'),
        'rgb'    : 'r8g8b8',
        'xrgb'   : 'x8r8g8b8',
        'rgba'   : 'r8g8b8a8',
    }
    
    # cache for bits per pixels
    _bpp = {}
    
    _yuv_pattern = re.compile(r"yuv\s?(\d):?(\d):?(\d)p?", re.I)
    
    def __new__(cls, description):
        '''description can be a name string, a plane description ar
        a tuple of plane descriptions.
        See PixelPlaneFormat.__new__ for details.
        Instances of PixelFormat are immutable and therefor can be used as dictionary
        keys. (There are just tuples with some additional methods.)
        '''
        planes = None
        if type(description) == str:
            # description is one of the pixel format names we know about?
            if description in cls._named_formats.keys():
                x = cls._named_formats[description]
                planes = cls._parse_description(x)
                # store normalized form in class dictionary
                cls._named_formats[description] = planes
                
        if planes is None:
            planes = cls._parse_description(description)
        return tuple.__new__(cls, planes)
            
    def _get_name(self):
        '''return a normalized string identifier that is accepted by __new__()'''
        for k,v in self._named_formats.items():
            if v == self:
                return k
        # XXX: synthesize a nicer name!
        # make sure __new__ accepts it!
        return str(self)
    name = property(_get_name, None)
           
    def _get_bits_per_pixel(self):
        '''return the number of bits required to store one pixel in this format'''
        if self in self._bpp.keys():
            return self._bpp[self]
            
        total = 0.0
        for p in self:
            plane_total = p._get_bits_per_sample()
            n, d, subsampling = p
            plane_total /= n * (lambda x, y: x*y)(*subsampling)
            total += plane_total
            
        PixelFormat._bpp[self] = total
        return total
    bits_per_pixel = property(_get_bits_per_pixel, None)
  
    is_planar = property(lambda self: len(self)>1)
    plane_count = property(lambda self: len(self))
    
    @classmethod
    def _parse_description(cls, description):
        if type(description) == str:
            yuv_format = cls._parse_yuv_name(description)
            if yuv_format:
                description = yuv_format
                
        if type(description) == tuple or type(description) == list:
            return cls._parse_planes(description)
        else:
            return (PixelPlaneFormat(description),)
 
    @classmethod        
    def _parse_yuv_name(cls, name):
        m = cls._yuv_pattern.match(name)
        if m:
            # see http://en.wikipedia.org/wiki/Chroma_subsampling
            # to understand this
            luma_width, chroma_samples_row1, chroma_samples_row2  = [int(x) for x in m.groups()]
            horizontal_subsampling = float(luma_width) / chroma_samples_row1
            vertical_subsampling = None
            if chroma_samples_row2 == 0:
                vertical_subsampling = 2
            elif chroma_samples_row2 == chroma_samples_row1:
                 vertical_subsampling = 1
            else:
                raise NotImplemented("chroma subsampling with different Y:Cr ratios for odd and even lines is not supported")
            subsampling = (horizontal_subsampling, vertical_subsampling)
            return ('y8', ('u8', subsampling), ('v8', subsampling))
        return None
   
    @classmethod        
    def _parse_planes(cls, one_or_more_planes):        
        # is it a single plane?
        try:
            return (PixelPlaneFormat(one_or_more_planes),)
        except MalformedPlaneFormat:
            pass # no, it wasn't
        
        planes = []
        for x in one_or_more_planes:
            t = PixelPlaneFormat(x)
            planes.append(t)
        return tuple(planes)
        

assert PixelFormat("rgb") == PixelFormat("rgb888")
assert PixelFormat("rgb888") == PixelFormat("r8g8b8")
assert PixelFormat("rgb") != PixelFormat("xrgb")

assert PixelFormat("uyvy") == ((2, (('y', ((8, 8), (24, 8))), ('u', ((0, 8),)), ('v', ((16, 8),))), (1, 1)),)


assert PixelFormat("rgb") == ((1, (('r', ((0, 8),)), ('b', ((16, 8),)), ('g', ((8, 8),))), (1, 1)),)

assert PixelFormat("yuv420p") == ((1, (('y', ((0, 8),)),), (1, 1)), (1, (('u', ((0, 8),)),), (2, 2)), (1, (('v', ((0, 8),)),), (2, 2)))


assert PixelFormat("YUV 4:2:0").name == "yuv420p"
assert PixelFormat("yuv420p") == PixelFormat("YUV 4:2:0")

assert PixelFormat._named_formats["rgb"] == PixelFormat("rgb")

assert PixelFormat("rgb").name == "rgb"
assert PixelFormat("rgb888").name == "rgb"
assert PixelFormat("r8g8b8").name == "rgb"

assert PixelFormat("rgb").bits_per_pixel == 24
assert PixelFormat("rgba").bits_per_pixel == 32
assert PixelFormat("uyvy").bits_per_pixel == 16
assert PixelFormat("yuv420p").bits_per_pixel == 12
assert PixelFormat("yuv420p").name == "yuv420p"
assert PixelFormat("rgb").is_planar == False
assert PixelFormat("rgb").plane_count == 1
assert PixelFormat("yuv420p").is_planar == True
assert PixelFormat("yuv420p").plane_count == 3
    
assert PixelFormat("YUV 4:4:0") == PixelFormat(('y8', ('u8',(1,2)), ('v8',(1,2))))
assert PixelFormat("YUV 4:4:4") == PixelFormat(('y8', 'u8', 'v8'))

    