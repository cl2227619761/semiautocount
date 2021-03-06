
import os

import numpy
from numpy import linalg
from scipy import ndimage
from skimage import morphology, color, segmentation, filter
#from PIL import Image

import nesoni
from nesoni import config

from . import images, stats, util, autocount_workspace

class Segmentation(object): pass


def segment_image(prefix, filename, min_area, blur):
    #import resource ; r = resource.getrusage(resource.RUSAGE_SELF)
    #print 'maxrss start', r.ru_maxrss

    image = images.load(filename)
    height = image.shape[0]
    width = image.shape[1]
    
    print prefix, 'FG/BG'
    
    blurred = filter.gaussian_filter(image, blur, multichannel=True)
    image_raveled = numpy.reshape(blurred,(height*width,3))
    del blurred
    
    # Allow for non-uniform lighting over image using a linear model
        
    #pred = [ ]
    #order = 2
    #for i in xrange(order):
    #    for j in xrange(order):
    #        pred.append((
    #            numpy.cos(numpy.linspace(0,numpy.pi*i, width)).astype('float32')[None,:] * 
    #            numpy.cos(numpy.linspace(0,numpy.pi*j, height)).astype('float32')[:,None]  ).ravel())    
    #pred = numpy.transpose(pred)
    
    #one = numpy.ones((height,width), dtype='float32').ravel()
    #x = numpy.empty((height,width), dtype='float32')
    #x[:,:] = numpy.linspace(0.0, 1.0, width)[None,:]
    #x = x.ravel()
    #y = numpy.empty((height,width), dtype='float32')
    #y[:,:] = numpy.linspace(0.0, 1.0, height)[:,None]
    #y = y.ravel()
    #pred = numpy.array((
    #    one,
    #    #x,
    #    #y,
    #    #x*x,
    #    #y*y,
    #    #x*y,
    #    #x*x*x,
    #    #y*y*y,
    #    #x*x*y,
    #    #y*y*x,
    #    )).transpose()    
    #del one,x,y
    #
    #def fit(mask):
    #    result = numpy.zeros((height*width,3), dtype='float32')
    #    for i in xrange(3):
    #        model = linalg.lstsq(pred[mask],image_raveled[mask,i])[0]
    #        for j in xrange(pred.shape[1]):
    #            result[:,i] += pred[:,j] * model[j]
    #    return result

    
    average = numpy.mean(image_raveled, axis=0)
    # Initial guess
    color_bg = (average*1.5) #[None,:]
    color_fg = (average*0.5) #[None,:]
    
    #offsets = image_raveled - average
    #icovar_fg = icovar_bg = stats.inverse_covariance(offsets)
    #mv_fg = mv_bg = stats.estimate_multivar(offsets)
    #mv = stats.estimate_indivar(offsets)
    #del offsets
    #p_fg = 0.5
    
    i = 0
    while True:
        #d_bg = a_raveled-color_bg[None,:]
        #d_bg *= d_bg
        #d_bg = numpy.sum(d_bg,1)
        #d_fg = a_raveled-color_fg[None,:]
        #d_fg *= d_fg
        #d_fg = numpy.sum(d_fg,1)
        #fg = d_fg*Background_weight < d_bg
        #color_fg = numpy.median(a_raveled[fg,:],axis=0)
        #color_bg = numpy.median(a_raveled[~fg,:],axis=0)    
        
        #d_bg = stats.length2s(icovar_bg, image_raveled - color_bg[None,:])
        #d_fg = stats.length2s(icovar_fg, image_raveled - color_fg[None,:])
        #fg = d_fg < d_bg
        
        #logp_bg = mv.logps(image_raveled - color_bg) #+ numpy.log(1.0-p_fg)
        #logp_fg = mv.logps(image_raveled - color_fg) #+ numpy.log(p_fg)
        #fg = logp_fg > logp_bg
        #del logp_bg, logp_fg
        
        mid = (color_bg+color_fg)*0.5
        proj = (color_fg-color_bg)
        fg = numpy.sum(image_raveled * proj[None,:], axis=1) > numpy.sum(mid*proj)
        
        #p_fg = numpy.mean(fg)
        #p_fg = max(0.05,min(0.95,p_fg))
        
        #print logp_bg[:10]
        #print logp_fg[:10]
        #print p_fg
        
        if i >= 5: break
        
        color_fg = numpy.mean(image_raveled[fg,:],axis=0)
        color_bg = numpy.mean(image_raveled[~fg,:],axis=0)
        
        #color_fg = fit(fg)
        #color_bg = fit(~fg)
        
        #offsets = image_raveled.copy()
        #offsets[fg,:] -= color_fg #[fg,:]
        #offsets[~fg,:] -= color_bg #[~fg,:]
        #mv = stats.estimate_indivar(offsets)
        #del offsets
        
        #mv_fg = mv_bg = stats.estimate_multivar(offsets)
        #icovar = stats.inverse_covariance(offsets)
        #icovar_fg = stats.inverse_covariance(image_raveled[fg,:] - color_fg[None,:])
        #icovar_bg = stats.inverse_covariance(image_raveled[~fg,:] - color_bg[None,:])
       # mv_fg = stats.estimate_multivar(image_raveled[fg,:] - color_fg[fg,:])
       # mv_bg = stats.estimate_multivar(image_raveled[~fg,:] - color_bg[~fg,:])
       
        i += 1
   
    fg = numpy.reshape(fg,(height,width))
    
    pred = None
    del color_fg,color_bg
        
    print prefix, 'Detect size'
    
    sizer = 1.0
    n1 = numpy.sum(fg)
    while True:
        n2 = numpy.sum(images.erode(fg, sizer))
        if n2 < n1*0.3: break
        sizer += 0.1
    print prefix, 'Size', sizer
    
    print prefix, 'Cleave'
    
    cores = images.cleave(fg, sizer)
    
    print prefix, 'Segment'
    
    core_labels, num_features = ndimage.label(cores)
    
    #dist = ndimage.distance_transform_edt(~cores)
    #dist = -ndimage.distance_transform_edt(fg)    
    dist = images.hessian(ndimage.gaussian_filter(fg.astype('float64'), sizer)).i1
    
    labels = morphology.watershed(dist, core_labels, mask=fg)


    #===
    #Remap labels to eliminate border cells and small cells
    
    bad_labels = set()
    for x in xrange(width):
        bad_labels.add(labels[0,x])
        bad_labels.add(labels[height-1,x])
    for y in xrange(height):
        bad_labels.add(labels[y,0])
        bad_labels.add(labels[y,width-1])
    
    threshold = sizer*sizer*min_area
    print prefix, 'Min cell area', threshold
    areas = numpy.zeros(num_features+1,'int32')
    for i in numpy.ravel(labels):
        areas[i] += 1
    for i in xrange(1,num_features+1):
        if areas[i] < threshold:
            bad_labels.add(i)
    
    
    mapping = numpy.zeros(num_features+1, 'int32')
    j = 1
    for i in xrange(1,num_features+1):
        if i not in bad_labels:
            mapping[i] = j
            j += 1
    labels = mapping[labels]
    
    bounds = [
        images.Rect(item[1].start,item[0].start,item[1].stop-item[1].start,item[0].stop-item[0].start)
        for item in ndimage.find_objects(labels)
        ]
    labels -= 1 #Labels start from zero, index into bounds
    
    print prefix, 'Saving'
    
    #test = color.label2rgb(labels-1, image)
    
    border = ndimage.maximum_filter(labels,size=(3,3)) != ndimage.minimum_filter(labels,size=(3,3))
    
    test = image.copy()
    test[border,:] = 0.0
    test[cores,:] *= 0.5
    test[cores,:] += 0.5
    #test[~fg,1] = 1.0
    #test[cores,2] = 1.0
    #test[:,:,1] = hatmax * 10.0
    #test[good,1] = hatmax

    #test[bounds[0]][:,:,1] = 1.0
    #test[labels == 0,2] = 1.0

    images.save(prefix+'-debug.png', test)
    
    #test2 = image.copy()
    #test2 /= numpy.reshape(color_fg, (height,width,3))
    #images.save(prefix+'-corrected.png', test2)
            
    images.save(prefix+'.png', image)
    
    result = Segmentation()
    result.n_cells = len(bounds)
    result.sizer = sizer
    result.labels = labels
    result.bounds = bounds
    util.save(prefix+'-segmentation.pgz', result)
    util.clear(prefix+'-measure.pgz')
    util.clear(prefix+'-classification.pgz')
    util.save(prefix+'-labels.pgz', [ None ] * result.n_cells)

    print prefix, 'Done'
    
    #import resource ; r = resource.getrusage(resource.RUSAGE_SELF)
    #print 'maxrss end', r.ru_maxrss



@config.help(
    'Create a Semiautocount working directory based on a set of images. '
    'Images are segmented into cells.',
    'ANY EXISTING IMAGES IN DIRECTORY WILL BE FORGOTTEN\n\n'
    'If your computer has limited memory and multiple cores, '
    'limit to a single core with --make-cores 1'
    )
@config.Float_flag('min_area',
    'Minimum cell area. '
    'Unit is relative to scaling constant derived from the image.'
    )
@config.Float_flag('blur',
    'Segmentation is performed on a blurred version of the image. This is the blur radius in pixels.'
    )
@config.Main_section('images',
    'Image filenames, or a directory containing images.'
    )
class Segment(config.Action_with_output_dir):
    _workspace_class = autocount_workspace.Autocount_workspace
    
    min_area = 4.0
    blur = 1.5
    images = [ ]

    def run(self):
        work = self.get_workspace()
        
        filenames = util.wildcard(self.images,['.png','.tif','.tiff','.jpg'])
        
        index = [ ]
        seen = set()
        for filename in filenames:
            name = os.path.splitext(os.path.basename(filename))[0]
            
            assert name not in seen, 'Duplicate image name: '+name
            seen.add(name)
            
            index.append(name)
        
        util.clear(work/('config','index.pgz'))

        with nesoni.Stage() as stage:        
            for name, filename in zip(index, filenames):
                stage.process(segment_image, work/('images',name), filename, min_area=self.min_area, blur=self.blur)

        util.save(work/('config','index.pgz'), index)

