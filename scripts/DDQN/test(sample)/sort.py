def split_and_save(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as file:
        content = file.read()

    # Split the content by ';' and remove any extra whitespace
    elements = content.split(';')

    with open(output_file, 'w', encoding='utf-8') as file:
        for element in elements:
            file.write(element.strip() + '\n')

# Example usage
input_file = 'SIMRESULT_TWO_TIER_WITH_EO_FUZZY_BASED_2000DEVICES_ALL_APPS_GENERIC.log'  # Replace with your input file name
output_file = '2000ALLL.log'  # Replace with your desired output file name
split_and_save(input_file, output_file)
