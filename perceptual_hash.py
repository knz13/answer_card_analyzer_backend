from PIL import Image
import imagehash
import os
import cv2

print(f"hashes = {{")
for file in os.listdir("perceptual_hash"):
    if file.endswith(".png"):


        image = cv2.imread(f"perceptual_hash/{file}")

        # upscale

        image = cv2.resize(image, (image.shape[1]*30, image.shape[0]*30),interpolation=cv2.INTER_NEAREST)

        # turn non black pixels to white
        
        _, threshold = cv2.threshold(image, 190, 255, cv2.THRESH_BINARY)
        image[threshold > 0] = 255
        image[threshold == 0] = 0


        # show image

        image = Image.fromarray(image)

        hash = imagehash.phash(image)

        print(f'"hash_{file[:-4]}":"{hash}"')

print(f"}}")