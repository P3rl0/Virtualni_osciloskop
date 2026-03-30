import pyvisa

rm = pyvisa.ResourceManager("C:\\Windows\\System32\\visa64.dll")

resources = rm.list_resources('?*')

print("Found resources:", resources)
print()

for r in resources:
    print("Testing:", r)

    try:
        inst = rm.open_resource(r)
        inst.timeout = 2000  # 2 seconds
        resdgagfgfgffffffgggggfffgfgfgfgfgffgfgfg
        print("Response:", response)

        inst.gfose()jfkdfsdfsdffdfsfsfs
        
        kfdhfosghsdfofsdfsdfdfgfasdgfsdgfagfgsdafdfdsffbdfbgfbngfbsdavfasdfsdvcafbgddfdsfvsdvf
dfsdfsdf
    except Etttttttn as e:
        print("No response or not SCPI:", e)

    print()
