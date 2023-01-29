'''
Module to process shopify data
Copyright 2023 Reyes Ruiz
'''
import sys
import json
import re
from com_digitalruiz_my_logger import my_logger
from com_digitalruiz_shopify_apis import shopify_apis as shopify

LOGGER = my_logger.set_logger(module_name=sys.argv[0], loglevel='INFO')

def add_product(product_dict):
    '''
    add product function
    '''
    shopify_product_json = {}
    product_id = ""
    variant_ids = []
    shopify_product_json['product'] = {'title': product_dict['title'], \
            'body_html': product_dict['description'], \
            'vendor': product_dict['vendor'], \
            'status': product_dict['status'], \
            'options': product_dict['options'], \
            'variants': product_dict['variants'], \
            'tags': product_dict['tags']}
    content = shopify.create_product(shopify_product_json)
    if content:
        shopify_product = json.loads(content)
        product_id = shopify_product['product']['id']
        for variant in shopify_product['product']['variants']:
            variant_ids.append(variant['id'])
        #sort_options(product_id)
        return product_id, variant_ids
    return False

def create_images(product_id, product_dict, variant_ids):
    '''
    create images
    '''
    shopify_images = shopify.get_shopify_images(product_id)
    for image in product_dict['images']:
        found = False
        md5 = image['md5']
        if shopify_images['images']:
            for shopify_image in shopify_images['images']:
                src = shopify_image['src']
                if md5 in src:
                    found = True
                    create_image_found(image, shopify_image, variant_ids, product_id)
        if not found:
            create_image_not_found(image, product_dict, variant_ids, product_id)

def create_image_found(image, shopify_image, variant_ids, product_id):
    '''
    Process found image
    '''
    image_dict = {}
    if image['featured']:
        image_dict['image'] = {}
        image_dict['image']['variant_ids']  = \
                shopify_image['variant_ids'] + variant_ids
        result = shopify.update_product_image(\
                product_id, shopify_image['id'], image_dict)
        if result:
            LOGGER.info("Successful image update of image id %s",\
                    shopify_image['id'])
        else:
            LOGGER.error("Unable to update image id %s", shopify_image['id'])


def create_image_not_found(image, product_dict, variant_ids, product_id):
    '''
    Process not found image
    '''
    image_dict = {}
    image_dict = {'image': {'alt': product_dict['color'], \
            'attachment': image['data'].decode('utf-8'), \
            'file_name': image['file_name'] \
            }}
    if image['featured']:
        image_dict['image']['variant_ids'] = variant_ids
    result = shopify.create_product_image(product_id, image_dict)
    if result:
        LOGGER.info("Successful Upload of image %s", image['file_name'])
    else:
        LOGGER.error("Unable to upload image %s", image['file_name'])

def add_variants(product_id, product_dict):
    '''
    add variants function
    '''
    variant_ids = []
    for variant in product_dict['variants']:
        variant_dict = {}
        variant_dict['variant'] = variant
        content = shopify.variants_create(product_id, variant_dict)
        if content:
            shopify_variant = json.loads(content)
            variant_ids.append(shopify_variant['variant']['id'])
    return variant_ids

def check_tags(shopify_tags_string, tags_string):
    '''
    check tags and updated them if needed
    '''
    shopify_tags = shopify_tags_string.split(',')
    shopify_tags = [s.strip() for s in shopify_tags]
    product_tags = tags_string.split(',')
    product_tags = [s.strip() for s in product_tags]
    final_tags = list(set(shopify_tags + product_tags))
    final_tags.sort()
    shopify_tags.sort()
    if final_tags == shopify_tags:
        return False
    return True

def check_product(product_id, product_dict):
    '''
    check product function
    '''
    LOGGER.info("Will process any new updates to product id %s", product_id)
    shopify_product_data = shopify.get_shopify_product_data(product_id)
    shopify_product_json = {}
    shopify_product_json['product'] = {}
    shopify_tags = shopify_product_data['product']['tags'].split(', ')
    product_tags = product_dict['tags'].split(',')
    final_tags = list(set(shopify_tags + product_tags))
    if all(tag in final_tags for tag in shopify_tags):
        LOGGER.info("No tags to update")
    else:
        tags_string = ','.join(str(e) for e in final_tags)
        LOGGER.info("Will update tags: %s", tags_string)
        shopify_product_json['product']['tags'] = tags_string
    if product_dict['description'] != shopify_product_data['product']['body_html']:
        LOGGER.info("Updating body html")
        shopify_product_json['product']['body_html'] = product_dict['description']
    #Update product:
    if shopify_product_json['product']:
        content = shopify.product_update(product_id, shopify_product_json)
        if content:
            LOGGER.info("Product update successfull")
        else:
            LOGGER.error("Unable to update product")

def check_variants(product_id, product_dict):
    '''
    Check variant function
    Checking if any information has changed for existing variants
    '''
    LOGGER.info("Will process any new updates for variants in product id %s", product_id)
    shopify_product_data = shopify.get_shopify_product_data(product_id)
    for shopify_variant in shopify_product_data['product']['variants']:
        for parsed_variant in product_dict['variants']:
            if 'option3' in parsed_variant.keys():
                if shopify_variant['option1'] == parsed_variant['option1'] \
                        and shopify_variant['option2'] == parsed_variant['option2'] \
                        and shopify_variant['option3'] == parsed_variant['option3']:
                    update_variant(parsed_variant, shopify_variant)
            else:
                if shopify_variant['option1'] == parsed_variant['option1'] \
                        and shopify_variant['option2'] == parsed_variant['option2']:
                    update_variant(parsed_variant, shopify_variant)

def check_new_variants(product_id, product_dict):
    '''
    Check if any new variant
    '''
    delete = []
    variant_ids = []
    shopify_product_data = shopify.get_shopify_product_data(product_id)
    for index, parsed_variant in enumerate(product_dict['variants']):
        for shopify_variant in shopify_product_data['product']['variants']:
            if 'option3' in parsed_variant.keys():
                if shopify_variant['option1'] == parsed_variant['option1'] \
                        and shopify_variant['option2'] == parsed_variant['option2'] \
                        and shopify_variant['option3'] == parsed_variant['option3']:
                    delete.append(index)
            else:
                if shopify_variant['option1'] == parsed_variant['option1'] \
                        and shopify_variant['option2'] == parsed_variant['option2']:
                    delete.append(index)
    if delete:
        for index in delete[::-1]:
            del product_dict['variants'][index]
    if product_dict['variants']:
        for variant in product_dict['variants']:
            variant_dict = {}
            variant_dict['variant'] = variant
            content = shopify.variants_create(product_id, variant_dict)
            if content:
                LOGGER.info("Success creating new variant")
                variant_ids.append(json.loads(content)['variant']['id'])
            else:
                LOGGER.error("Unable to create new variant")
    return variant_ids

def update_variant(parsed_variant, shopify_variant):
    '''
    update variant
    '''
    variant_dict = {}
    variant_dict['variant'] = {}
    #Price
    if float(shopify_variant['price']) != float(parsed_variant['price']):
        LOGGER.info("Price difference, changing from %s to %s", \
                shopify_variant['price'], parsed_variant['price'])
        variant_dict['variant']["price"] =  parsed_variant['price']
    #Barcode checking if it is none or empty, dont want to change something that is already set
    if shopify_variant['barcode'] == "None" \
            or shopify_variant['barcode'] == "" \
            or not shopify_variant['barcode']:
        if str(shopify_variant['barcode']) != str(parsed_variant['barcode']):
            LOGGER.info("UPC difference, changing from %s to %s", \
                    shopify_variant['barcode'], parsed_variant['barcode'])
            #variant_dict['variant']["barcode"] =  parsed_variant['barcode']
    if variant_dict['variant']:
        LOGGER.info("Updating variant %s", shopify_variant['id'])
        variant_dict['variant']['id'] = shopify_variant['id']
        content = shopify.variant_update(variant_dict)
        if content:
            LOGGER.info("Success in updating variant %s", shopify_variant['id'])
        else:
            LOGGER.error("Something went wrong updates variant %s", shopify_variant['id'])

def sort_options(product_id):
    '''
    Function to sort options
    '''
    shopify_product_data = shopify.get_shopify_product_data(product_id)
    product_dict = {}
    product_dict['product'] = {"options": shopify_product_data['product']['options']}
    product_dict['product']['options'][1]['values'] = \
            merge_sort(product_dict['product']['options'][1]['values'])
    if len(product_dict['product']['options']) == 3:
        product_dict['product']['options'][2]['values'] =\
                merge_sort(product_dict['product']['options'][2]['values'])
    shopify.product_update(product_id, product_dict)

def merge_sort_variants(arr_var):
    '''
    merge sort variant array
    '''
    if len(arr_var) > 1:
        match_digits = re.search(r'^\d*$', arr_var[0]['option2'])
        if not match_digits:
            return arr_var
        mid = len(arr_var)//2
        left = arr_var[:mid]
        right = arr_var[mid:]
        merge_sort_variants(left)
        merge_sort_variants(right)
        i = j = k = 0
        while i < len(left) and j < len(right):
            match_left = re.search(r'^(\d*\.\d*|\d*)', left[i]['option2'])
            size_left = float(match_left.group(1))
            match_right = re.search(r'^(\d*\.\d*|\d*)', right[j]['option2'])
            size_right = float(match_right.group(1))
            if size_left < size_right:
                arr_var[k] = left[i]
                i += 1
            else:
                arr_var[k] = right[j]
                j += 1
            k += 1
        while i < len(left):
            arr_var[k] = left[i]
            i += 1
            k += 1
        while j < len(right):
            arr_var[k] = right[j]
            j += 1
            k += 1
    return arr_var

def merge_sort(arr):
    '''
    merge sort
    '''
    if len(arr) > 1:
        mid = len(arr)//2
        left = arr[:mid]
        right = arr[mid:]
        merge_sort(left)
        merge_sort(right)
        i = j = k = 0
        while i < len(left) and j < len(right):
            match_left = re.search(r'^(\d*\.\d*|\d*)', left[i])
            size_left = float(match_left.group(1))
            match_right = re.search(r'^(\d*\.\d*|\d*)', right[j])
            size_right = float(match_right.group(1))
            if size_left < size_right:
                arr[k] = left[i]
                i += 1
            else:
                arr[k] = right[j]
                j += 1
            k += 1
        while i < len(left):
            arr[k] = left[i]
            i += 1
            k += 1
        while j < len(right):
            arr[k] = right[j]
            j += 1
            k += 1
    return arr

def check_barcodes():
    '''
    module to check barcodes and print if there are duplicates
    '''
    duplicates = []
    barcodes = []
    products = shopify.get_all_products()
    for product in products:
        for variant in product['variants']:
            barcode = variant['barcode']
            if barcode and barcode in barcodes:
                duplicates.append(barcode)
            barcodes.append(barcode)
    if duplicates:
        for duplicate in duplicates:
            LOGGER.warning("Duplicate barcode found: %s", duplicate)
    else:
        LOGGER.info("No duplicate barcodes found")
    return duplicates

def generate_barcodes(product_id):
    '''
    module to generate barcodes using shopify variant id as barcode
    return False if there is any error, else return True
    '''
    result = {}
    result['status'] = "Success"
    result['product_id'] = product_id
    result['variants'] = []
    product_data = shopify.get_shopify_product_data(product_id)
    result['title'] = product_data['product']['title']
    for shopify_variant in product_data['product']['variants']:
        variant_dict = {}
        variant_dict['variant'] = {}
        variant_dict['variant']['id'] = shopify_variant['id']
        if shopify_variant['barcode'] == "None" or \
                shopify_variant['barcode'] == "" \
                or not shopify_variant["barcode"]:
            variant_dict['variant']['barcode'] = shopify_variant['id']
            content = shopify.variant_update(variant_dict)
            if content:
                LOGGER.info("Success in updating variant %s", shopify_variant['id'])
                variant_dict['variant']['status'] = "Success"
            else:
                LOGGER.error("Something went wrong in updating variant %s", shopify_variant['id'])
                variant_dict['variant']['status'] = "Failed"
                result['status'] = "Failed"
        else:
            variant_dict['variant']['status'] = "Exists"
        variant_dict['variant']['title'] = shopify_variant['title']
        result['variants'].append(variant_dict['variant'])
    return result

def find_variant_by_barcode(barcode, products = None):
    '''
    Function to find variant by barcode
    '''
    if not products:
        products = shopify.get_all_products()
    if products:
        for product in products:
            for variant in product['variants']:
                variant_barcode = variant['barcode']
                if barcode == variant_barcode:
                    return variant
        return False
    return False
