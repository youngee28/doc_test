import os
import zipfile
import argparse

def repackage_hwpx(input_dir, output_file):
    """
    Compresses the contents of input_dir into a valid HWPX (ZIP) file.
    """
    try:
        # Check if input directory exists
        if not os.path.isdir(input_dir):
            print(f"Error: Input directory '{input_dir}' does not exist.")
            return False

        # Create the output zip file
        with zipfile.ZipFile(output_file, 'w') as zf:
            print(f"Repackaging '{input_dir}' to '{output_file}'...")
            
            # Priority/Compression mapping based on original HWPX analysis
            # mimetype: must be first, STORED
            # version.xml: STORED
            # Preview/PrvImage.png: STORED
            # Others: DEFLATED
            
            items_to_store = ["mimetype", "version.xml", "Preview/PrvImage.png"]
            
            # Standard timestamp (1980-01-01 00:00:00) to match original
            fixed_time = (1980, 1, 1, 0, 0, 0)
            
            # 1. mimetype (MUST BE FIRST)
            mimetype_path = os.path.join(input_dir, "mimetype")
            if os.path.exists(mimetype_path):
                zinfo = zipfile.ZipInfo("mimetype", date_time=fixed_time)
                zinfo.compress_type = zipfile.ZIP_STORED
                with open(mimetype_path, "rb") as f:
                    zf.writestr(zinfo, f.read())
            
            # 2. Walk and add others
            for root, dirs, files in os.walk(input_dir):
                for file in files:
                    rel_path = os.path.relpath(os.path.join(root, file), start=input_dir)
                    if rel_path == "mimetype":
                        continue
                    
                    full_path = os.path.join(root, file)
                    zinfo = zipfile.ZipInfo(rel_path, date_time=fixed_time)
                    
                    if rel_path in items_to_store:
                        zinfo.compress_type = zipfile.ZIP_STORED
                    else:
                        zinfo.compress_type = zipfile.ZIP_DEFLATED
                        
                    with open(full_path, "rb") as f:
                        zf.writestr(zinfo, f.read())
        
        print(f"Successfully created '{output_file}'")
        return True

    except Exception as e:
        print(f"Error creating HWPX: {e}")
        return False
