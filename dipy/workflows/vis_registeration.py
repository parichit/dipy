from __future__ import division, print_function, absolute_import
from dipy.workflows.workflow import Workflow
import logging
import numpy as np
import nibabel as nib
from dipy.workflows.core import write_gif
from dipy.io.image import load_affine_matrix
from dipy.viz.regtools import overlay_slices
from dipy.viz import (window, actor)

from dipy.viz.window import snapshot


class VisualizeRegisteredImage(Workflow):

    def process_image_data(self, static_img, moved_img, type_vis):

        """
        Function for pre-processing the image data. It involves
        normalizing and copying static, moving images in the
        red and green channel, respectively.

        type_vis: str
            The type of visualisation being created. This affects the
            range of values to be selected from the moved image.

        return: the normalized image data and range of pixels to be
        selected.
        """

        static_img = 255 * ((static_img - static_img.min()) /
                            (static_img.max() - static_img.min()))
        moved_img = 255 * ((moved_img - moved_img.min()) /
                           (moved_img.max() - moved_img.min()))

        # Create the color images
        overlay = np.zeros(shape=(static_img.shape) + (3,), dtype=np.uint8)
        overlay[..., 0] = static_img
        overlay[..., 1] = moved_img
        mean, std = overlay[overlay > 0].mean(), overlay[overlay > 0].std()
        if type_vis == 'mosaic':
            value_range = (mean - 0.5 * std, mean + 1.5 * std)
        elif type_vis == 'anim':
            value_range = (mean - 0.5 * std, mean + 1.5 * std)

        return overlay, value_range

    def get_row_cols(self, num_slices):

        """
        Experimetal helper function to get the number
        of rows and columns for the mosaic.

        num_slices: int
            The number of slices as obtained from the
            create_mosaic function.
        return: the number of rows and columns.
        """
        rows, cols = 0, 0

        while True:
            if num_slices % 5 == 0:
                break
            num_slices += 1

        for i in range(5, num_slices):

            if num_slices % i == 0:
                rows = i
                cols = num_slices // i
                break

        return rows, cols

    def create_mosaic(self, static_img, moved_img,
                      affine, fname):
        """
        Function for creating the mosaic of the moved image. It
        currently only supports slices from the axial plane.

        fname: str, optional
            Filename to be used for saving the mosaic (default 'mosaic.png').
        """

        overlay, value_range = self.process_image_data(static_img,
                                                       moved_img,
                                                       'mosaic')

        renderer = window.Renderer()
        renderer.background((0.5, 0.5, 0.5))

        slice_actor = actor.slicer(overlay, affine, value_range)
        renderer.projection('parallel')

        cnt = 0
        _, _, num_slices = slice_actor.shape[:3]

        rows, cols = self.get_row_cols(num_slices)
        border = 5

        for j in range(rows):
            for i in range(cols):
                slice_mosaic = slice_actor.copy()
                slice_mosaic.display(None, None, cnt)
                slice_mosaic.SetPosition((X + border) * i,
                                         0.5 * cols * (Y + border) -
                                         (Y + border) * j, 0)
                slice_mosaic.SetInterpolate(False)
                renderer.add(slice_mosaic)
                renderer.reset_camera()
                renderer.zoom(1.6)
                cnt += 1
                if cnt > num_slices:
                    break
            if cnt > num_slices:
                break

        renderer.reset_camera()
        renderer.zoom(1.6)

        window.record(renderer, out_path=fname,
                      size=(900, 600), reset_camera=False)

    def adjust_color_range(self, img):

        """
        Function to adjust the range of colors in numpy array
        to create the GIF (GIF standard only supports 256 colours).

        return
        The numpy array with scaled down range of color values.
        """

        # Interpoloating to range 0-15 for reducing the colours.
        img[..., 0] = np.interp(img[..., 0], (img[..., 0].min(), img[..., 0].max()),
                                 (0, 15))
        img[..., 1] = np.interp(img[..., 1], (img[..., 1].min(), img[..., 1].max()),
                                 (0, 15))
        img = np.round(img, 0).astype('uint8')

        # Interpolating back to the range 0-255 for getting GIF range.
        img[..., 0] = np.interp(img[..., 0], (img[..., 0].min(), img[..., 0].max()),
                                 (0, 255))
        img[..., 1] = np.interp(img[..., 1], (img[..., 1].min(), img[..., 1].max()),
                                 (0, 255))

        return img

    def animate_overlap(self, static_img, moved_img, sli_type, fname):

        """
        Function for creating the animated GIF from the slices of the
        registered image. This function does not perform any
        orientation correction or quality optimisation. Please see
        'animate_overlap_with_renderer' for visualising the correct
        orientation.

        Patameters
        ----------
        sli_type : str (optional)
            the type of slice to be extracted:
            sagital, coronal, axial, None (default).
        fname: str, optional
            Filename for saving the GIF (default 'animation.gif').
        """

        overlay, value_range = self.process_image_data(static_img,
                                                       moved_img,
                                                       'anim')
        x, y, z, _ = overlay.shape

        overlay = overlay.astype('uint8')

        # Selecting the pixels based on the obtained value range.
        overlay = np.interp(overlay, xp=[value_range[0], value_range[1]],
                            fp=[0, 255])
        num_slices = 0

        if sli_type == 'saggital':
            num_slices = x
            slice_type = 0
        elif sli_type == 'coronal':
            num_slices = y
            slice_type = 1
        elif sli_type == 'axial':
            num_slices = z
            slice_type = 2

        slices = []

        for i in range(num_slices):
            temp_slice = overlay_slices(overlay[..., 0], overlay[..., 1],
                                        slice_type=slice_type,
                                        slice_index=i, ret_slice=True)
            slices.append(temp_slice)

        # Writing the GIF below
        write_gif(slices, fname, fps=10)

    def animate_overlap_with_renderer(self, static_img, moved_img,
                                      sli_type, fname, affine):

        """
        Function for creating the animated GIF from the slices of the
        registered image. It uses the renderer object to control the
        dimensions of the created GIF and for correcting the orientation.
        Patameters
        ----------
        sli_type : str (optional)
            the type of slice to be extracted:
            sagital, coronal, axial, None (default).

        fname: str, optional
            Filename for saving the GIF (default 'animation.gif').
        """

        overlay, value_range = self.process_image_data(static_img,
                                                       moved_img, 'anim')
        x, y, z, _ = overlay.shape

        num_slices = 0

        if sli_type == 'saggital':
            num_slices = x
            slice_type = 0
        elif sli_type == 'coronal':
            num_slices = y
            slice_type = 1
        elif sli_type == 'axial':
            num_slices = z
            slice_type = 2

        # Creating the renderer object and setting the background.
        renderer = window.renderer((0.5, 0.5, 0.5))
        slices = []

        for i in range(num_slices):
            temp_slice = overlay_slices(overlay[..., 0], overlay[..., 1],
                                        slice_type=slice_type,
                                        slice_index=i, ret_slice=True)
            temp_slice = temp_slice[..., None]
            temp_slice = np.round(temp_slice,0).astype('uint8')
            temp_slice = np.rollaxis(temp_slice, 2, 4)
            slice_actor = actor.slicer(temp_slice, affine, value_range)
            renderer.add(slice_actor)
            renderer.reset_camera()
            renderer.zoom(1.6)
            snap = snapshot(renderer)
            snap = self.adjust_color_range(snap)
            slices.append(snap)

        # Writing the GIF below
        write_gif(slices, fname, fps=10)

    @staticmethod
    def check_dimensions(static, moving):

        """Check the dimensions of the input images."""

        if len(static.shape) != len(moving.shape):
            raise ValueError('Dimension mismatch: The'
                             ' input images must have same number of '
                             'dimensions.')

    def run(self, static_img_file, moving_img_file, affine_matrix_file,
            show_mosaic=False, anim_slice_type=None, out_dir='',
            mosaic_file='mosaic.png', animate_file='animation.gif'):
        """
        Parameters
        ----------
        static_img_file : string
            Path to the reference image.

        moving_img_file : string
            Path to the moving image file.

        affine_matrix_file : string
            The text file containing the affine matrix for transformation.

        show_mosaic : bool, optional
            If enabled, a mosaic of the all the slices from the
            axial plane is saved in an image (default False).

        anim_slice_type : str, optional
            A GIF animation showing the overlap of slices
            from static and moving images will be saved.
            sagital, coronal, axial, None (default).

        out_dir : string, optional
            Directory to save the results (default '').

        mosaic_file : string, optional
            Name of the file to save the mosaic (default 'mosaic.png').

        animate_file : string, optional
            name of the html file for saving the animation
            (default animation.gif).

        """

        io_it = self.get_io_iterator()

        for static_img, mov_img, affine_matrix_file in io_it:

            # Load the data from the input files and store into objects.

            image = nib.load(static_img)
            static = image.get_data()

            image = nib.load(mov_img)
            moved_image = image.get_data()

            # Load the affine matrix from the input file and
            # store into numpy object.
            affine_matrix = load_affine_matrix(affine_matrix_file)

            # Do a sanity check on the number of dimensions.
            self.check_dimensions(static, moved_image)

            # Call the create_mosaic function if a valid option was provided.
            if show_mosaic:
                self.create_mosaic(static, moved_image, affine_matrix,
                                   mosaic_file)

            if anim_slice_type is not None:
                self.animate_overlap_with_renderer(static, moved_image,
                                                   anim_slice_type,
                                                   animate_file, affine_matrix)
            if not show_mosaic and anim_slice_type is None:
                logging.info('No options supplied. Exiting.')
