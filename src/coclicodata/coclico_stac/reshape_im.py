# %%
import os
import cv2
import glob
import pathlib


def reshape_aspectratio_image(image_file_path, aspect_ratio=16 / 9):
    """
    Function that reshapes an image based on cv2. The image is not compressed but
    cropped to the desired aspect ratio with respect to the centre of the image. By default 16:9 aspect ratio is set.

    """
    # Read image file
    im = cv2.imread(image_file_path)

    if im.shape[0]/im.shape[1] == aspect_ratio:
        print('Image is already cropped to the aspect ratio')
        return im

    # In case of too wide for aspect ratio
    if im.shape[0] / im.shape[1] < (1 / aspect_ratio):
        # Determine the indexes for a square image
        middle_column = im.shape[1] / 2
        left_column = round(middle_column - im.shape[0] / (aspect_ratio) / 2)
        right_column = round(middle_column + im.shape[0] / (aspect_ratio) / 2)
        # Crop image
        square_im = im[:, left_column:right_column]

    # In case of image too long for aspect ratio
    else:
        # Determine the indexes for a square image
        middle_row = im.shape[0] / 2
        top_row = round(middle_row - im.shape[1] / (aspect_ratio) / 2)
        bottom_row = round(middle_row + im.shape[1] / (aspect_ratio) / 2)
        # Crop image
        square_im = im[top_row:bottom_row, :]

    return square_im
    

if __name__ == "__main__":

    # define local directories
    home = pathlib.Path().home()
    in_path = home.joinpath(r"Documents\GitHub\coclicodata\scripts\thumbnails")
    list_png = glob.glob(str(in_path.joinpath("*.png")))

    # loop over images
    for png in list_png:

        cropped_im = reshape_aspectratio_image(png, aspect_ratio=16 / 9)
        cv2.imwrite(
            os.path.join(in_path, "square", png.split("\\")[-1].replace("png", "jpeg")),
            cropped_im,
        )
# %%
