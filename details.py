import re

class MalformedPlaneFormat(Exception):
    pass

class PixelFormat(tuple):
    '''PixelFormat describes the layout of one or more planes of pixel data'''
    
    _named_formats = {
        'yuv420p': ('y8', ('u8', (2,2)), ('v8', (2,2))),
        'yuv422p': ('y8', ('u8', (2,1)), ('v8', (2,1))),
        'uyvy'   : (2, 'u8y8v8y8'),
        'rgb'    : 'r8g8b8',
        'xrgb'   : 'x8r8g8b8',
        'rgba'   : 'r8g8b8a8',
    }
    
    _layput_pattern1 = re.compile(r"(?:[a-zA-Z]\d+)+")
    _find_pattern1 = re.compile(r"([a-zA-Z])(\d+)")

    _layput_pattern2 = re.compile(r"([a-zA-Z]+)(\d+)")
    
    def __new__(cls, description):
        '''description can be a name, a plane description ar a tuple of plane descriptions
           plane descriptions are tuples (n, layout, (x-divisor, y-divisor))
           where n is the number of pixels described (usually one or two)
           layout is a string that describes the dstribution of channel bits inside n pixels
           x-divisor and y-divisor are horizontal and vertical subsampling factors
           if n is one, it can be omitted
           if subsampling is (1,1) it can be omitted     
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
        for k,v in self._named_formats.items():
            if v == self:
                return k
        return None
    name = property(_get_name, None)
       
    def _get_bits_per_sample(self, plane):
        if type(plane) == int:
            plane = self(plane)
        plane_total = 0.0
        n, d, subsampling = plane
        for channel in d.values():
            for start, width in channel:
                plane_total += width
        return plane_total
    
    def _get_bits_per_pixel(self):
        total = 0.0
        for p in self:
            plane_total = self._get_bits_per_sample(p)
            n, d, subsampling = p
            plane_total /= n * (lambda x, y: x*y)(*subsampling)
            total += plane_total
        return total
    bits_per_pixel = property(_get_bits_per_pixel, None)
  
    is_planar = property(lambda self: len(self)>1)
    plane_count = property(lambda self: len(self))
    
    @classmethod   
    def _parse_description(cls, description):
        if type(description) == tuple or type(description) == list:
            return cls._parse_planes(description)
        else:
            return cls._parse_planes((description,))
    
    @classmethod        
    def _parse_planes(cls, one_or_more_planes):
        cls._planes = []
        
        # is it a single plane?
        t = cls._parse_plane(one_or_more_planes)
        if t is not None: 
            n, layout, subsampling = t
            channels = cls._parse_layout(layout)
            if channels is not None:
                return [(n, channels, subsampling)]
        
        planes = []
        for x in one_or_more_planes:
            t = cls._parse_plane(x)
            
            try:
                n, layout, subsampling = t
            except TypeError:
                raise MalformedPlaneFormat()
                
            planes.append((n, cls._parse_layout(layout), subsampling))
        return tuple(planes)
    
    @classmethod
    def _parse_plane(cls, x):
        t = None
        if type(x) == str:
            t = 1, x, (1,1)
        elif type(x) == tuple:
            if len(x) == 3:
                t = x
            if len(x) == 2:
                if (type(x[0])==str or type(x[0])==dict) and type(x[1])==tuple:
                    t = (1,) + x
                elif type(x[0]) == int and (type(x[1]) == str or type(x[1])==dict):
                    t = x + ((1,1),)
        return t
    
    @classmethod
    def _parse_layout(cls, s):
        if type(s) == dict:
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
        return d
    
    
        
print PixelFormat("rgb") == PixelFormat("rgb888")
print PixelFormat("rgb888") == PixelFormat("r8g8b8")
print PixelFormat("rgb") != PixelFormat("xrgb")

print PixelFormat("uyvy")
print PixelFormat._named_formats["rgb"]
print PixelFormat("rgb").name
print PixelFormat("rgb").bits_per_pixel
print PixelFormat("uyvy").bits_per_pixel
print PixelFormat("yuv420p").bits_per_pixel
print PixelFormat("yuv420p").name
print PixelFormat("rgb").is_planar
print PixelFormat("rgb").plane_count
print PixelFormat("yuv420p").is_planar
print PixelFormat("yuv420p").plane_count




    