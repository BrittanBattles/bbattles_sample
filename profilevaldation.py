# Copy paste this code into the "validation" tab when creating an ArcGIS Pro Script tool

import arcpy
import re

routes = r"\\mplgis_server\gis_data\Connections\SDE_INTREPID-PROD.sde\sde_intrepid.sde.M_V_SC_CENTERLINE"
substitute = r'\((.*)\)'
subbed_system_list = []
final_system_list = []

class ToolValidator(object):
    """Class for validating a tool's parameter values and controlling
    the behavior of the tool's dialog."""

    def __init__(self):
        """Setup arcpy and the list of tool parameters.""" 
        self.params = arcpy.GetParameterInfo()

    def initializeParameters(self): 
        """Refine the properties of a tool's parameters. This method is 
        called when the tool is opened."""
        
        with arcpy.da.SearchCursor(routes, 'system_name') as cursor:
            system_list = sorted({row[0] for row in cursor})
            for item in system_list:
                subbed_system_val = re.sub(substitute, '', item)
                subbed_system_list.append(item)
                # subbed_system_list.append(subbed_system_val)
                for value in subbed_system_list:
                    if value not in final_system_list:
                        final_system_list.append(value)
            self.params[4].filter.list = final_system_list
            
            with arcpy.da.SearchCursor(routes, 'segment_group_name') as cursor:
                route_list = sorted({str(row[0]) for row in cursor})
            self.params[3].filter.list = route_list


    def updateParameters(self):
        """Modify the values and properties of parameters before internal
        validation is performed. This method is called whenever a parameter
        has been changed."""
        
        if self.params[0].value == 'DEM':
            self.params[5].enabled = True
        else:
            self.params[5].enabled = False
            
        if self.params[1].value == 'Segment Group':
            self.params[3].enabled = True
        else:
            self.params[3].enabled = False
            
        if self.params[1].value == 'System':
            self.params[4].enabled = True
        else:
            self.params[4].enabled = False
        
            
    def updateMessages(self):
        """Modify the messages created by internal validation for each tool
        parameter. This method is called after internal validation."""
