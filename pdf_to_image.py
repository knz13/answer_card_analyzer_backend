
from pdf2image import convert_from_path

if __name__ == "__main__":

    images = convert_from_path("alignment_corrector/examples/Resp_1_2_DIA_MODELO.pdf")

    images[1].save("image_6.png", "PNG")