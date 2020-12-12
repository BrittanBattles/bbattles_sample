# import modules
import arcpy
import os
import pandas as pd

# Set the geoprocessing workspace
gdb = r"\\mplgis_server\gis_data\Tools\Prod\ArcGISProTools\Default.gdb"
arcpy.env.workspace = gdb

# set working extent, this is due to sde-intrepid extents being wrong
arcpy.env.extent = "MAXOF"
arcpy.env.overwriteOutput = True

# set user defined parameters
method = arcpy.GetParameterAsText(0)
feature_category = arcpy.GetParameterAsText(1)
output_file_path = arcpy.GetParameterAsText(2)
segments = arcpy.GetParameter(3)
systems = arcpy.GetParameter(4)
dem_intersect_interval = arcpy.GetParameter(5)

# set local variables
contour_5ft = r"\\mplgis_server\serverImagery\Imagery\NED\cont_5ft\NED\DEM_3RD_ARCSEC_5ft.gdb\All_Contours"
rid_field = "route_id"
routes = r"\\mplgis_server\gis_data\Connections\SDE_INTREPID-PROD.sde\sde_intrepid.sde.M_V_SC_CENTERLINE"
route_copy = os.path.join(gdb, "route_copy")
out_table = os.path.join(gdb, "out_table")
csv_table = output_file_path
props = "rid_field POINT meas"
first_last_csv = r'\\mplgis_server\gis_data\Tools\Prod\Profile\firstlast.csv'
table_folder = r'\\mplgis_server\gis_data\Tools\Prod\Profile\Tables'
ROUTE_FL = "ROUTE_FL"
BUFFER_FL = "BUFFER_FL"
CLIPPED_CONTOUR_FL = "CLIPPED_CONTOUR_FL"
INTERSECT_POINTS_FL_MP = "INTERSECT_POINTS_FL_MP"
INTERSECT_POINTS_FL = "INTERSECT_POINTS_FL"
route_list = []
ROUTE_EVENT_LAYER = "ROUTE_EVENT_LAYER"
third_arc_second_raster = r'\\MPSSHR01.MGroupNet.com\GIS_Imagery\ThirdArcSecondDEM\c3rdas_1'


def clear_out():
    # clear out existing log-data in the project folder
    logging_fc = arcpy.ListFeatureClasses()
    logging_tables = arcpy.ListTables()
    for fc in logging_fc:
        arcpy.Delete_management(fc)
    for table in logging_tables:
        arcpy.Delete_management(table)
    arcpy.AddMessage("Debugging Environment Reset")


def get_route_list():
    if feature_category == 'Segment Group':
        for segment in segments:
            with arcpy.da.SearchCursor(routes, ['segment_group_name', 'route_id', 'route_stage']) as cursor:
                for row in cursor:
                    if row[2] in ('0', '1', '3', '4', '5') and segment == row[0]:
                        route_list.append(int(row[1]))
                        arcpy.AddMessage(str(int(row[1])) + " added to route list")
        arcpy.AddMessage(str(len(route_list)) + " Selected Segment Groups")

    if feature_category == 'System':
        for system in systems:
            with arcpy.da.SearchCursor(routes, ['system_name', 'route_id', 'route_stage']) as cursor:
                for row in cursor:
                    if row[2] in ('0', '1', '3', '4', '5') and system == row[0]:
                        route_list.append(int(row[1]))
                        arcpy.AddMessage(str(int(row[1])) + " added to route list")
        arcpy.AddMessage(str(len(route_list)) + " Selected Segment Groups")

    if feature_category == 'All Systems/Segments':
        with arcpy.da.SearchCursor(routes, ['route_id', 'route_stage']) as cursor:
            for row in cursor:
                if row[1] in ('0', '1', '3', '4', '5'):
                    route_list.append(int(row[0]))
                    arcpy.AddMessage(str(int(row[0])) + " added to route list")

    return route_list


def copy_routes():
    # copy desired route from sde-intrepid to a feature layer
    py_route_where = """{} IN {}""".format(rid_field, route_list)
    # arcpy.AddMessage(py_route_where)
    sql_route_where = py_route_where.replace('[', '(').replace(']', ')')
    # arcpy.AddMessage(sql_route_where)
    arcpy.MakeFeatureLayer_management(routes, ROUTE_FL, sql_route_where)
    arcpy.CopyFeatures_management(ROUTE_FL, route_copy)
    arcpy.AddMessage("Route Query Complete")
    return route_list


def get_contour():
    # buffer the queried route by 1 foot
    arcpy.Buffer_analysis(ROUTE_FL, BUFFER_FL, buffer_distance_or_field="1 Feet", dissolve_option="NONE")
    # arcpy.CopyFeatures_management(BUFFER_FL, os.path.join(gdb, "buffer"))  # for testing, comment out when not in use
    arcpy.AddMessage("Buffer Complete")

    # clip the contours with the buffer
    arcpy.AddMessage("Clipping Contours....")
    arcpy.Clip_analysis(contour_5ft, BUFFER_FL, CLIPPED_CONTOUR_FL)
    arcpy.CopyFeatures_management(CLIPPED_CONTOUR_FL, os.path.join(gdb, "CONTOUR"))
    arcpy.AddMessage("Contour Clip Complete")

    # intersect Queried Route with Clipped Contour to generate points for loading
    arcpy.AddMessage("Intersecting Contours with Route....")
    arcpy.Intersect_analysis([ROUTE_FL, CLIPPED_CONTOUR_FL], INTERSECT_POINTS_FL_MP, "ALL", 0, "POINT")
    arcpy.AddMessage("Intersect Complete")

    # explode multipart features
    arcpy.AddMessage("Exploding Multipart Features....")
    arcpy.MultipartToSinglepart_management(INTERSECT_POINTS_FL_MP, INTERSECT_POINTS_FL)
    arcpy.AddMessage("Explode Complete")

    # locate the intersected points along the route and give them a measure value
    arcpy.AddMessage("Locating Features Along Route.....")
    arcpy.LocateFeaturesAlongRoutes_lr(INTERSECT_POINTS_FL, route_copy, rid_field, "50 Feet",
                                       out_table, props, "FIRST")
    arcpy.AddMessage("Locate Complete")


def create_contour_table():
    # create field list from our output table
    field_list = [f.name for f in arcpy.ListFields(out_table)]
    arcpy.AddMessage("Field List Compiled")

    # load output table into a numpy array, to prepare the data for pandas
    arcpy.AddMessage("Building Array....")
    table_array = arcpy.da.FeatureClassToNumPyArray(out_table, field_list)
    arcpy.AddMessage("Array Complete")

    # load output table into pandas data frame
    arcpy.AddMessage("Building Data Frame.....")
    intersect_df = pd.DataFrame(table_array)

    # create a table inside of the debugging environment to represent the first and last points of a route
    arcpy.AddMessage("Calculating First/Last Profile Points")
    contour_df = pd.DataFrame(columns=['Contour', 'meas', 'route_id'])
    with arcpy.da.SearchCursor(route_copy, ['Beg_Measure', 'End_Measure', 'route_id']) as cursor:
        for row in cursor:
            beg_measure = row[0]
            end_measure = row[1]
            route_id = int(row[2])
            type_begin = 'begin'
            type_end = 'end'
            query_expression = """route_id == {}""".format(route_id)
            query_df = intersect_df.query(query_expression)
            beg_end_data = {'meas': [beg_measure, end_measure], 'route_id': [route_id, route_id],
                            'type': [type_begin, type_end]}
            row_df = pd.DataFrame(data=beg_end_data)
            row_df = row_df.append(query_df, sort=True)
            row_df = row_df.sort_values(['meas'], ascending=[True])
            row_df['Contour'].iat[0] = row_df['Contour'].iat[1]
            row_df['Contour'].iat[-1] = row_df['Contour'].iat[-2]
            contour_df = contour_df.append(row_df, sort=True)
    contour_df.rename(columns={'Contour': 'elevation', 'meas': 'measure'}, inplace=True)
    contour_df.drop(columns=['Beg_Measure', 'Description', 'Distance', 'End_Measure', 'FID_CLIPPED_CONTOUR_FL',
                         'FID_M_V_SC_CENTERLINE', 'Id', 'Line_id', 'OBJECTID', 'ORIG_FID', 'designator', 'rid_field',
                         'route_stage', 'segment_group_name', 'system_name', 'type'], inplace=True)
    contour_df = contour_df.round({'elevation': 2})
    contour_df = contour_df[['measure', 'route_id', 'elevation']]
    contour_df = contour_df.astype({'route_id': 'int64'})

    # remove duplicate values if one happens to be generated
    contour_df.drop_duplicates(subset=['measure', 'route_id'], keep="first", inplace=True)

    # output data frame to csv
    arcpy.AddMessage("Outputting to csv.....")
    contour_df.to_csv(csv_table)
    arcpy.AddMessage("csv complete")


def get_dem_intersect():
    with arcpy.da.SearchCursor(route_copy, ['route_id', 'End_Measure']) as cursor:
        for row in cursor:
            interval_num = dem_intersect_interval
            route_id = int(row[0])
            end_measure = row[1]
            row_number = int(row[1] / interval_num)
            csv_path = os.path.join(table_folder, str(route_id) + '.csv')
            df = pd.DataFrame({'measure': [0], 'route_id': [route_id]})
            if row_number == 1:
                df_50 = pd.DataFrame(({'measure': [interval_num], 'route_id': [route_id]}))
                df = df.append(df_50, ignore_index=True)
            if row_number > 1:
                i = 1
                while i < row_number + 1:
                    df_row = pd.DataFrame(({'measure': [interval_num * i], 'route_id': [route_id]}))
                    df = df.append(df_row, ignore_index=True)
                    i = i + 1
            df_end_measure = pd.DataFrame(({'measure': [end_measure], 'route_id': [route_id]}))
            df = df.append(df_end_measure, ignore_index=True)
            df.to_csv(csv_path)
            arcpy.AddMessage("Table Creation Complete: " + csv_path)
            arcpy.AddMessage("Row number: " + str(row_number + 2))
            arcpy.MakeRouteEventLayer_lr(in_routes=route_copy, route_id_field='route_id', in_table=csv_path,
                                         in_event_properties="route_id POINT measure", out_layer=ROUTE_EVENT_LAYER)
            arcpy.CopyFeatures_management(ROUTE_EVENT_LAYER, os.path.join(gdb, 'profile_REL_' + str(route_id)))
            arcpy.AddMessage('Route Event Layer Created: ' + str(route_id))
            arcpy.sa.ExtractValuesToPoints(os.path.join(gdb, 'profile_REL_' + str(route_id)),
                                           third_arc_second_raster, os.path.join(gdb, 'profile_' + str(route_id)))
            arcpy.AddField_management(os.path.join(gdb, 'profile_' + str(route_id)), 'elevation', "DOUBLE")
            arcpy.AddMessage('Calculating the Elevation field: ' + str(route_id))
            with arcpy.da.UpdateCursor(os.path.join(gdb, 'profile_' + str(route_id)), ['RASTERVALU', 'elevation']) \
                    as updater:
                for route in updater:
                    elevation = route[0] * 3.28084
                    route[1] = elevation
                    updater.updateRow(route)
        arcpy.AddMessage('Merging outputs....')
        profile_output_list = []
        output_fcs = arcpy.ListFeatureClasses()
        for output in output_fcs:
            if 'REL' in output or 'route_copy' in output:
                arcpy.Delete_management(output)
            else:
                profile_output_list.append(output)
        arcpy.Merge_management(profile_output_list, 'merged_profiles')
        arcpy.CopyRows_management('merged_profiles', 'merge_table')

        arcpy.AddMessage('Outputs merged')
        field_list = [f.name for f in arcpy.ListFields('merge_table')]
        arcpy.AddMessage("Field List Compiled")

        # load output table into a numpy array, to prepare the data for pandas
        arcpy.AddMessage("Building Array....")
        table_array = arcpy.da.FeatureClassToNumPyArray('merged_profiles', field_list)
        arcpy.AddMessage("Array Complete")

        # load output table into pandas data frame
        arcpy.AddMessage("Building Data Frame.....")
        dem_df = pd.DataFrame(table_array)
        dem_df.drop(columns=['OBJECTID', 'Field1', 'RASTERVALU'], inplace=True)
        dem_df.sort_values(['route_id', 'measure'], ascending=[True, True], inplace=True)
        dem_df = dem_df.round({'elevation': 2})

        # remove duplicate values if one happens to be generated
        dem_df.drop_duplicates(subset=['measure', 'route_id'], keep="first", inplace=True)

        # output data frame to csv
        arcpy.AddMessage("Outputting to csv.....")
        dem_df.to_csv(output_file_path)
        arcpy.AddMessage("csv complete")

# execute profile extraction


if __name__ == "__main__":
    clear_out()
    get_route_list()
    copy_routes()
    if method == 'Contour':
        get_contour()
        create_contour_table()
    if method == 'DEM':
        get_dem_intersect()






