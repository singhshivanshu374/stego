#Steganography

import cv2 

def spiltbyte(by): #011 000 01
    first_three_bits = by >> 5
    mid_three_bits = (by >> 2) & 7
    last_two_bits = by & 3
    return first_three_bits, mid_three_bits, last_two_bits

def merge_bits(bits) : #[3,0, 1] => 97
    # result = bits[0] <<3 #make room for 3 bits at the RHS
    # result = result | bits[1] #merge the mid 3 bits
    # result = result << 2 #make room for 2 bits at the RHS
    # result = result | bits[2] #merge the mid 2 bits

    return (((bits[0]<<3) | bits[1]) << 2) | bits[2]


def embed(vessel_image, target_image):
    #load the vessel_image into memory
    mem_image = cv2.imread(vessel_image)
    print(type(mem_image))
    print(mem_image.shape)

    #dummy data to embed
    data = [x for x in range(65,91)]
    print(data)
    size = len(data)
    indx = 0

    #embedding loop
    r =0
    while r < mem_image.shape[0] and indx < size:
        c =0
        while c < mem_image.shape[1] and indx < size:
            bits = spiltbyte(data[indx])

            #Free 2,3,3 bits of the pixel
            mem_image[r, c, 0] &= 252  #blue band
            mem_image[r, c, 1] &= 248  #green band
            mem_image[r, c, 2] &= 248  #red band

            #Merge the bits into the bands
            mem_image[r, c, 0] |= bits[2]  # blue band
            mem_image[r, c, 1] |= bits[1]  # green band
            mem_image[r, c, 2] |= bits[0]  # red band

            #next val to embed
            indx+=1

            c+=1
        r+=1

    #save back the image
    cv2.imwrite(target_image, mem_image)
def extract(emb_image):
    mem_img = cv2.imread(emb_image)
    qty_to_extract = 26
    width = mem_img.shape[1]
    buffer = []
    indx = 0

    while indx < qty_to_extract:
        r = indx // width
        c = indx % width

        red_bits = mem_img[r, c, 2] & 0b111
        green_bits = mem_img[r, c, 1] & 0b111
        blue_bits = mem_img[r, c, 0] & 0b11

        original_byte = merge_bits([red_bits, green_bits, blue_bits])
        buffer.append(original_byte)
        indx += 1

    return buffer

def main():
    vessel_image_path = "C:/Users/ROHIT/Downloads/snake.jpg"
    target_image_path = "C:/Users/ROHIT/Downloads/new_snake.png"
    embed(vessel_image_path, target_image_path)
    buffer = extract(target_image_path)
    py_list = [int(x) for x in buffer]
    print(py_list)
    print(''.join(chr(val) for val in buffer))

main()

