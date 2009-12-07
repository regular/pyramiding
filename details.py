import re
from collections import namedtuple

class MalformedPlaneFormat(ValueError):
    pass

class PixelPlaneFormat(namedtuple("PixelPlaneFormat", "span channels subsampling")):
    '''PixelFormat describes the layout of one plane of pixel data. See __new__ for
       details.
    '''
    __slots__ = ()
    
    _layput_pattern1 = re.compile(r"(?:[a-zA-Z]\d+)+")
    _find_pattern1 = re.compile(r"([a-zA-Z])(\d+)")
    
    _layput_pattern2 = re.compile(r"([a-zA-Z]+)(\d+)")
    
    @classmethod
    def from_description(cls, plane_description):
        '''A plane descriptions is a tuple (n, layout, (x-divisor, y-divisor))
           where n is the number of pixels described (the pixel_span, usually one or two)
           layout is a string that describes the dstribution of channel bits inside n pixels
           x-divisor and y-divisor are horizontal and vertical subsampling factors.
           if n is one, it can be omitted
           if subsampling is (1,1) it can be omitted, too.
           Layout can have one or two forms:
           <char><int><char><int> ...
           or
           <char><char><char> ... <int><int><int> ...
           Where <char> is a single character indicating the 'name' of a color channel
           (like r, g, b, a, y, u, v, l etc)
           and n is a number indicating the number of bits this channel uses.
           In the second form the number of bits is restricted to a single digit (1-9).
        '''
        
        t = cls._parse_plane(plane_description)
        if t is None:
            raise MalformedPlaneFormat("invalid plane descrition: %s" % plane_description)
        return cls._make(t)
    
    @property
    def bits_per_sample(self):
        '''return number of bits per sample in this plane.'''
        plane_total = 0.0
        n, layout, subsampling = self
        for channel, fractions in layout:
            for start, width in fractions:
                plane_total += width
        return plane_total
   
    def __repr__(self):
        name = self.name
        if name is not None:
            return "'%s'" % name
        span, channels, subsampling = self
        s = ""
        if span != 1:
            s += "%d, " % span
        
        chs = []
        for name, pos in channels:
            if len(pos)==1 and pos[0][0]==0:
                ch = "'%s%d'" % (name, pos[0][1])
            else:
                ch = "('%s', %s)" % (name,repr(pos))
            chs.append(ch)
        chs = ", ".join(chs)
        if len(channels) > 1:
            chs = "(%s)" % chs
        s+= chs
        if subsampling != (1,1):
            s += ", " + repr(subsampling)

        s = '(%s)' %s
        return s     
    
    @property
    def name(self):
        n, channels, subsampling = self
        # if n is one and subsampling is (1,1)
        # we simply concatente channel names and bit widths in order
        if n==1 and subsampling==(1,1):
            sorted_channels = [(pos, name) for name, pos in channels]
            sorted_channels.sort()
            i = 0
            result=""
            for pos, name in sorted_channels:
                if len(pos)>1:
                    # uh, the channel is not a continous range in memory
                    result = None
                    break
                start, width = pos[0]
                if start != i:
                    result=None
                    break
                result += "%s%d" % (name, width)
                i += width
            if result:
                return result
        return None
    
    ## private implementation
    
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
                if type(x[0]) == int and (type(x[1]) == str or type(x[1])==tuple):
                    t = x + ((1,1),)
                elif (type(x[0])==str or type(x[0])==tuple) and type(x[1])==tuple:
                    # can x[1] be a subsampling spec?
                    # XXX this is ugly
                    if len(x[1]) == 2 and type(x[1][0])  in (int, float) and type(x[1][1]) in (int, float): 
                        t = (1,) + x
        
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
                    raise MalformedPlaneFormat("invalid channel layout: %s" % s)
                channels = zip(names, widths)
            else:
                raise MalformedPlaneFormat("invalid channel layout: %s" % s)
        
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
    
    __slots__ = ()
    
    # The tuples and names below can be considered
    # examples of different forms of valied PixelFormat descriptors that can be
    # passed to PixelFormat.__new__
    _named_formats = dict(
        rgb         = 'r8g8b8',
        xrgb        = 'x8r8g8b8',
        rgba        = 'r8g8b8a8',

        gray8       = 'y8', # Y, 8bpp
        monowhite   = 'k1', # Y, 1bpp, 0 is white, 1 is black
        monoblack   = 'y1', # Y, 1bpp, 0 is black, 1 is white
        pal8        = 'i8', # 8 bit with RGB32 palette
        
        uyvy422     = (2, 'u8y8v8y8'),      # XXX UV or VU? XXX Packed YUV 4:2:2, 16bpp, Cb Y0 Cr Y1     
        yuyv422     = (2, 'y8u8y8v8'),      # Packed YUV 4:2:2, 16bpp, Y0 Cb Y1 Cr
        uyyvyy411   = (4, 'u8y8y8v8y8y8'),  # Packed YUV 4:1:1, 12bpp, Cb Y0 Y1 Cr Y2 Y3

        yuva420p    = ('y8', ('u8', (2,2)), ('v8', (2,2)), 'a8'),   # Planar YUV 4:2:0, 20bpp, (1 Cr & Cb sample per 2x2 Y & A samples)
        nv12        = ('y8', ('u8v8', (2, 2))), # Planar YUV 4:2:0, 12bpp, 1 plane for Y and 1 for UV
        nv21        = ('y8', ('v8u8', (2, 2))), # as above, but U and V bytes are swapped

        # generic formats don't need to be declared
        #yuv422p    = ''    # Planar YUV 4:2:2, 16bpp, (1 Cr & Cb sample per 2x1 Y samples)
        #yuv444p    = ''    # Planar YUV 4:4:4, 24bpp, (1 Cr & Cb sample per 1x1 Y samples)
        #yuv410p    = ''    # Planar YUV 4:1:0,  9bpp, (1 Cr & Cb sample per 4x4 Y samples)
        #yuv411p    = ''    # Planar YUV 4:1:1, 12bpp, (1 Cr & Cb sample per 4x1 Y samples)
        #yuv440p    = ''    # Planar YUV 4:4:0 (1 Cr & Cb sample per 1x2 Y samples)

        # Jpeg specific formats not yet supported
        #yuvj420p   = ''    # Planar YUV 4:2:0, 12bpp, full scale (jpeg)
        #yuvj422p   = ''    # Planar YUV 4:2:2, 16bpp, full scale (jpeg)
        #yuvj444p   = ''    # Planar YUV 4:4:4, 24bpp, full scale (jpeg)     
        #yuvj440p   = ''    # Planar YUV 4:4:0 full scale (jpeg)

        # XXX need a way to express endianness 
        # rgb32     = 'x8r8g8b',    # Packed RGB 8:8:8, 32bpp, (msb)8A 8R 8G 8B(lsb), in cpu endianness
        # rgb24     = 'r8g8b8', # Packed RGB 8:8:8, 24bpp, RGBRGB...
        # bgr24     = 'b8g8r8', # Packed RGB 8:8:8, 24bpp, BGRBGR...
        # bgr32     = 'x8b8g8r8',   # Packed RGB 8:8:8, 32bpp, (msb)8A 8B 8G 8R(lsb), in cpu endianness
        # bgr565    = 'b5g6r5'  # Packed RGB 5:6:5, 16bpp, (msb)   5B 6G 5R(lsb), in cpu endianness
        # bgr555    = 'x1b5g5r5'    # Packed RGB 5:5:5, 16bpp, (msb)1A 5B 5G 5R(lsb), in cpu endianness most significant bit to 1
        # rgb565        = 'r5g6b5', # Packed RGB 5:6:5, 16bpp, (msb)   5R 6G 5B(lsb), in cpu endianness
        # bgr8      = 'b3g3r2', # Packed RGB 3:3:2,  8bpp, (msb)2B 3G 3R(lsb)
        # bgr4      = 'b1g2r1', # Packed RGB 1:2:1,  4bpp, (msb)1B 2G 1R(lsb)
        # bgr4_byte = 'r1g2b1', # Packed RGB 1:2:1,  8bpp, (msb)1B 2G 1R(lsb)
        # rgb8      = 'r3g3b2', # Packed RGB 3:3:2,  8bpp, (msb)2R 3G 3B(lsb)
        # rgb4      = 'r1g2b1', # Packed RGB 1:2:1,  4bpp, (msb)2R 3G 3B(lsb)
        # rgb4_byte = 'r1g2b1', # Packed RGB 1:2:1,  8bpp, (msb)2R 3G 3B(lsb)
        
        # rgb32_1   = '',   # Packed RGB 8:8:8, 32bpp, (msb)8R 8G 8B 8A(lsb), in cpu endianness
        # bgr32_1   = '',   # Packed RGB 8:8:8, 32bpp, (msb)8B 8G 8R 8A(lsb), in cpu endianness
        # gray16be  = '',   #        Y        , 16bpp, big-endian
        # gray16le  = '',   #        Y        , 16bpp, little-endian
    )
    
    # cache for bits per pixels
    _bpp = {}
    
    _yuv_pattern = re.compile(r"yuv\s?(\d):?(\d):?(\d)p?", re.I)
    
    def __new__(cls, description):
        '''description can be a name string, a plane description ar
        a tuple of plane descriptions.
        See PixelPlaneFormat.from_description() for details.
        If the last character of a name string is 'p' each channel
        is considered to be on its own plane.
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
    
    @property
    def name(self):
        '''return a normalized string identifier that is accepted by __new__()'''
        for k,v in self._named_formats.items():
            if v == self:
                return k
        
        result = self._make_yuv_name(self)
        if result is not None:
            return result
        
        if len(self) == 1:
            return self[0].name
        else:
            plane_names = [p.name for p in self]
            if None not in plane_names:
                return "".join(plane_names)+"p"
        return str(self)
    
    @property
    def bits_per_pixel(self):
        '''return the number of bits required to store one pixel in this format'''
        if self in self._bpp.keys():
            return self._bpp[self]
        
        total = 0.0
        for p in self:
            plane_total = p.bits_per_sample
            n, d, subsampling = p
            plane_total /= n * (lambda x, y: x*y)(*subsampling)
            total += plane_total
        
        PixelFormat._bpp[self] = total
        return total
    
    is_planar = property(lambda self: len(self)>1)
    plane_count = property(lambda self: len(self))
    
    ## private implementation
    
    @classmethod
    def _parse_description(cls, description):
        make_planar = False
        if type(description) == str:
            yuv_format = cls._parse_yuv_name(description)
            if yuv_format:
                description = yuv_format
            else:
                if description[0]=="(" and description[-1] == ")":
                    # evaluate repr string in a sondbox without __builtins__
                    result = eval(description, dict(__builtins__=None), dict(PixelPlaneFormat=PixelPlaneFormat))
                    if type(result) == tuple:
                        description = result
                
                elif description[-1].lower()=="p":
                    make_planar=True
                    description = description[:-1]
        
        if type(description) == tuple or type(description) == list:
            result = cls._parse_planes(description)
        else:
            result = (PixelPlaneFormat.from_description(description),)
        
        if make_planar:
            result = cls._make_planar(result)
        return result
    
    @classmethod
    def _make_planar(cls, t):
        '''convert a given non-planar format into a planar format
           by putting each channel on a separate plane.
           If channels are not continous within a pixel,
           there will be one plane per continois region.
        '''
        assert len(t)==1
        n, channels, subsampling = t[0]
        
        sorted_channels = [] # [(pos, name)]
        for name, pos in channels:
            sorted_channels += zip(pos, [name]*len(pos))
        
        sorted_channels.sort()
        planes = []
        for pos, name in sorted_channels:
            start, width = pos
            planes.append(
                PixelPlaneFormat(
                    n,
                    (
                        ( name, ((0, width),) ),
                    ),
                    subsampling
                )
            )
        return tuple(planes)
    
    @classmethod
    def _make_yuv_name(cls, t):
        # is this a planar yuv format at all?
        if not t.is_planar:
            return None
        
        # we only have names for formats with one channel per
        # plane that has a width of 8 bits
        components = []
        for plane in t:
            if len(plane.channels) != 1:
                return
            name, pos = plane.channels[0]
            name = name.lower()
            
            if len(pos) != 1:
                return None
            start, width = pos[0]
            if start != 0 or width != 8:
                return None
            
            if name not in "yuv":
                return None
            
            components.append((name, plane.subsampling))
        
        # do we have a channel on more than one plane?
        names = [name for name, ss in components]
        if len(names) != len(set(names)):
            return None
        
        if len(components) != 3:
            return None
        
        components = dict(components)
        
        # y component must have full resolution
        if components['y'] != (1,1):
            return None
        
        # chromo components must have the same subsampling
        if components['u'] != components['v']:
            return None
        
        # okay, we will be able to name the beast
        chroma_subsampling = components['u']
        luma_width = chroma_subsampling[0]
        chroma_samples_row1 = 1
        if chroma_subsampling[1] == 1:
            chroma_samples_row2 = chroma_samples_row1
        else:
            chroma_samples_row2 = 0
        
        numbers = [luma_width, chroma_samples_row1, chroma_samples_row2]
        m = max(numbers)
        if m<3:
            # normalize to luma_width == 4
            numbers = map(lambda x: x*4/m, numbers)
        return "%s%s%s%d%d%dp" % tuple(names + numbers)
    
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
            # prefer int over float, if possible
            subsampling = tuple([int(x) if x==round(x) else x for x in subsampling])
            return ('y8', ('u8', subsampling), ('v8', subsampling))
        return None
    
    @classmethod
    def _parse_planes(cls, one_or_more_planes):
        # is it a single plane?
        try:
            return (PixelPlaneFormat.from_description(one_or_more_planes),)
        except MalformedPlaneFormat:
            pass # no, it wasn't
        
        planes = []
        for x in one_or_more_planes:
            t = PixelPlaneFormat.from_description(x)
            planes.append(t)
        return tuple(planes)


assert PixelFormat("rgb") == PixelFormat("rgb888")
assert PixelFormat("rgb888") == PixelFormat("r8g8b8")
assert PixelFormat("rgb") != PixelFormat("xrgb")

assert PixelFormat("uyvy422") == ((2, (('y', ((8, 8), (24, 8))), ('u', ((0, 8),)), ('v', ((16, 8),))), (1, 1)),)

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
assert PixelFormat("uyvy422").bits_per_pixel == 16
assert PixelFormat("yuv420p").bits_per_pixel == 12
assert PixelFormat("yuv420p").name == "yuv420p"
assert PixelFormat("rgb").is_planar == False
assert PixelFormat("rgb").plane_count == 1
assert PixelFormat("yuv420p").is_planar == True
assert PixelFormat("yuv420p").plane_count == 3

assert PixelFormat("YUV 4:4:0") == PixelFormat(('y8', ('u8',(1,2)), ('v8',(1,2))))
assert PixelFormat("YUV 4:4:4") == PixelFormat(('y8', 'u8', 'v8'))

assert PixelFormat("l8").name == PixelFormat("l8p").name
assert PixelFormat(PixelFormat("rgb888").name) == PixelFormat("rgb888")
assert PixelFormat(PixelFormat("rgb888p").name) == PixelFormat("rgb888p")

assert PixelFormat("yuv888p").name == "yuv444p"
assert PixelFormat("yuv844p").name == "yuv422p"
assert PixelFormat("yuv840p").name == "yuv420p"
assert PixelFormat(PixelFormat("yuv888p").name) == PixelFormat("yuv888p")

assert PixelFormat("nv12").bits_per_pixel == 12
assert PixelFormat("nv12")[1].bits_per_sample == 16

# a format without a name:
planes = PixelFormat("yuv420p")
pf = PixelFormat((planes[0]._replace(subsampling=(2,2)), planes[1], planes[2]))
assert pf == PixelFormat(pf.name)

# XX YUV format names get a special treatment
# no yuv format, numbers are interpreted as bit widths
# rather than a subsampling specification:
# XXX maybe it is a good idea to drop postfix bit width specification because of this

assert PixelFormat("yua422p").name == 'y4u2a2p'


