from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import QgsCheckableComboBox, QgsFeatureListComboBox, QgsFieldExpressionWidget
from qgis.utils import *
from qgis.utils import iface

import os.path
from pathlib import Path
import re
from .config import *
import processing
from .qt_json_view.model import JsonModel, JsonSortFilterProxyModel
from .qt_json_view.view import JsonView
from functools import partial
import json

# Import the code for the DockWidget
from .filter_mate_dockwidget import FilterMateDockWidget

class FilterMateApp:

    PROJECT_LAYERS = {} 


    def __init__(self):
        self.iface = iface
        self.dockwidget = None
        self.flags = {}
        self.run()


    def run(self):
        if self.dockwidget == None:

            init_layers = list(PROJECT.mapLayers().values())

            self.manage_project_layers(init_layers, 'add')

            self.dockwidget = FilterMateDockWidget(self.PROJECT_LAYERS)

            """Controller for populating and keep updated comboboxes"""
            self.populate = populateData(self.dockwidget)


            # """Controller for dealing with filter widgets and the configuration model"""
            # self.managerWidgets = ManagerWidgets(self.dockwidget)

            # """Init the filter widgets"""
            # self.managerWidgets.manage_widgets(CONFIG_DATA['WIDGETS'])

            """Init the advanced filters"""
            self.populate.populate_predicat()
            self.populate.populate_layers()

            # show the dockwidget
            # TODO: fix to allow choice of dock location
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
            self.dockwidget.show()


        """Keep the advanced filter combobox updated on adding or removing layers"""

        PROJECT.layersAdded.connect(partial(self.manage_project_layers, 'add'))
        PROJECT.layersWillBeRemoved.connect(partial(self.manage_project_layers, 'remove'))

        #PROJECT.loadingLayer.connect(partial(self.manage_flags, 'layers', 'loadingLayer'))
        PROJECT.legendLayersAdded.connect(partial(self.manage_flags, 'layers', 'legendLayersAdded'))
        PROJECT.layersRemoved.connect(partial(self.manage_flags, 'layers', 'layersRemoved'))



        
        self.dockwidget.launchingTask.connect(self.manage_task)

        #self.dockwidget.gettingProjectLayers.connect(partial(self.dockwidget.get_project_layers_from_app, self.PROJECT_LAYERS))

        self.dockwidget.settingProjectLayers.connect(self.set_project_layers_from_dockwidget)

        
        """Overload configuration qtreeview model to keep configuration file up to date"""
        # self.managerWidgets.model.dataChanged.connect(self.qtree_signal)
        # self.managerWidgets.model.rowsInserted.connect(self.qtree_signal)
        # self.managerWidgets.model.rowsRemoved.connect(self.qtree_signal)


        # self.managerWidgets.view.onLeaveEvent.connect(self.reload_config)
        #self.managerWidgets.view.onAddWidget.connect(lambda: self.reload_config('add'))
        #self.managerWidgets.view.onRemoveWidget.connect(lambda: self.reload_config('remove'))
    def manage_flags(self, flag_type, flag):
        if flag_type == 'layers':
            if flag == 'loadingLayer':
                self.flags['is_managing_project_layers'] = True
            elif flag == 'legendLayersAdded':
                self.flags['is_managing_project_layers'] = False
            elif flag == 'layersRemoved':
                self.flags['is_managing_project_layers'] = False


    def set_project_layers_from_dockwidget(self, project_layers):
        if isinstance(project_layers, dict):
            self.PROJECT_LAYERS = project_layers
            


    def manage_project_layers(self, layers, action):

        self.flags['is_managing_project_layers'] = True

        self.json_template_layer_infos = '{"layer_type":"%s","layer_crs":"%s","layer_id":"%s","layer_name":"%s","primary_key_name":"%s","primary_key_idx":%s,"primary_key_type":"%s","primary_key_is_numeric":%s}'
        self.json_template_layer_meta = '{"is_saving":false,"is_tracking":false,"is_selecting":false,"is_already_subset":false,"single_selection":{"expression":"%s"},"multiple_selection":{"expression":"%s"},"custom_selection":{"expression":"%s"} }'
        
        for layer in layers:
            if action == 'add':     
                self.add_project_layer(layer)
            elif action == 'remove':
                self.remove_project_layer(layer)


        if self.dockwidget != None:
            self.dockwidget.get_project_layers_from_app(self.PROJECT_LAYERS) 
            
        self.flags['is_managing_project_layers'] = False


    def add_project_layer(self, layer):


        if layer.id() not in self.PROJECT_LAYERS.keys():

            if isinstance(layer, QgsVectorLayer) and layer.isSpatial():
        
                primary_key_name, primary_key_idx, primary_key_type, primary_key_is_numeric = self.search_primary_key_from_layer(layer)

                if layer.providerType() == 'ogr':

                    capabilities = layer.capabilitiesString().split(', ')
                    if 'Transactions' in capabilities:
                        layer_type = 'spatialite'
                    else:
                        layer_type = 'ogr'

                elif layer.providerType() == 'postgres':
                    layer_type = 'postgresql'

                else:
                    capabilities = layer.capabilitiesString().split(', ')
                    if 'Transactions' in capabilities:
                        layer_type = 'spatialite'
                    else:
                        layer_type = 'ogr'

                layer_infos = json.loads(self.json_template_layer_infos % (layer_type, layer.sourceCrs().authid(), layer.id(), layer.name(), primary_key_name, primary_key_idx, primary_key_type, str(primary_key_is_numeric).lower()))
                layer_meta = json.loads(self.json_template_layer_meta % (str(primary_key_name),str(primary_key_name),str(primary_key_name)))

                self.PROJECT_LAYERS[str(layer.id())] = {"infos": layer_infos, "meta": layer_meta}


    def remove_project_layer(self, layer_id):
        try:
            del self.PROJECT_LAYERS[layer_id]
            
        except:
            print("Layer id not found")

    def search_primary_key_from_layer(self, layer):
        """For each layer we search the primary key"""

        primary_key_index = layer.primaryKeyAttributes()
        if len(primary_key_index) > 0:
            for field_id in primary_key_index:
                if len(layer.uniqueValues(field_id)) == layer.featureCount():
                    field = layer.fields()[field_id]
                    return field.name(), field_id, field.typeName(), field.isNumeric()
        else:
            for field in layer.fields():
                if 'ID' in str(field.name()).upper():
                    if len(layer.uniqueValues(layer.fields().indexOf(field.name()))) == layer.featureCount():
                        return field.name(), field.id(), field.typeName(), field.isNumeric()
                    
            for field in layer.fields():
                if len(layer.uniqueValues(layer.fields().indexOf(field.name()))) == layer.featureCount():
                    return field.name(), field.id(), field.typeName(), field.isNumeric()


    def manage_task(self, task_name):
        """Manage the different tasks"""

        self.tasks_descriptions = {'filter':'Filtering data',
                                    'unfilter':'Unfiltering data',
                                    'export':'Exporting data'}
        
        assert task_name in list(self.tasks_descriptions.keys())
        
        #params = self.serialize_parameters(task_name)

        t0 = time.time()
        self.task = FilterEngineTask(self.tasks_descriptions[task_name], task_name, params)

        if task_name == 'start':
            layer_name = self.dockwidget.mMapLayerComboBox_filter_by_selection.currentText()
            self.layer_zoom = PROJECT.mapLayersByName(layer_name)[0]
            self.task.taskCompleted.connect(lambda: zoom_to_features(self.layer_zoom, t0))

        QgsApplication.taskManager().addTask(self.task)

    # def serialize_parameters(self, task_name):

    #     if task_name == 'filter':

    #         selected_layers_data = self.dockwidget.comboBox_select_layers.checkedItems()
    #         self.filter_multi = self.dockwidget.checkBox_multi_filter.checkState()
    #         self.filter_add = self.dockwidget.checkBox_filter_add.checkState()
    #         self.from_operator = self.dockwidget.comboBox_filter_add.currentText()
    #         self.filter_add_multi = self.dockwidget.checkBox_add_multi.checkState()
    #         self.multi_operator = self.dockwidget.comboBox_filter_add_multi.currentText()
    #         self.current_index = self.dockwidget.current_index
    #         avance = self.dockwidget.checkBox_filter_layer.checkState()
    #         self.filter_geo = self.dockwidget.checkBox_filter_geo.checkState()
    #         with_tampon = self.dockwidget.checkBox_tampon.checkState()
    #         predicats = self.dockwidget.mComboBox_filter_geo.checkedItems()
    #         distance = float(self.dockwidget.mQgsDoubleSpinBox_tampon.value())

    #         expression = self.dockwidget.mFieldExpressionWidget.currentText()

    #         expression = expression.replace("'", "\'")
    #         layer_name = self.dockwidget.mMapLayerComboBox_filter_by_selection.currentText()

    #     elif task_name == 'unfilter':

    #         selected_layers_data = self.dockwidget.comboBox_select_layers.checkedItems()

    #     elif task_name == 'export':    

    #         selected_layers_data = self.dockwidget.comboBox_select_layers.checkedItems()
    #         format = self.dockwidget.comboBox_export_type.currentText()
    #         name = str(self.dockwidget.lineEdit_export.text()) if self.dockwidget.lineEdit_export.text() != '' else 'output'
    #         crs = self.dockwidget.mQgsProjectionSelectionWidget.crs()



class ManagerWidgets:
    """Controller for dealing with filter widgets and the configuration model"""

    def __init__(self, dockwidget):

        self.dockwidget = dockwidget
        self.populate = populateData(self.dockwidget)
        self.widgets = []
        self.dockwidget.WIDGETS.setLayout(QVBoxLayout())
        self.layout = self.dockwidget.WIDGETS.layout()
        self.run()

    def run(self):
        """Manage the qtreeview model configuration"""
        self.manage_configuration_model()



    def manage_configuration_model(self):
        """Manage the qtreeview model configuration"""
        #self.proxy = JsonSortFilterProxyModel()
        self.model = JsonModel(data=CONFIG_DATA, editable_keys=True, editable_values=True)

        #self.proxy.setSourceModel(self.model)
        self.view = JsonView(self.model)
        self.dockwidget.CONFIGURATION.layout().addWidget(self.view)
        #self.view.setModel(self.model)
        self.view.setModel(self.model)


        self.view.setAnimated(True)
        self.view.setDragDropMode(QAbstractItemView.InternalMove)
        self.view.show()
        self.view.setStyleSheet("""padding:0px;
                                    color:black;""")


    def manage_widgets(self, widgets):
        """Manage the filter widgets"""


        for i in reversed(range(self.layout.count())):
            try:

                layout_item = self.layout.itemAt(i)

                if layout_item.itemAt(i) is not None:

                    self.remove_widget(layout_item, i)
            except:
                pass
            #self.dockwidget.removeItem(self.dockwidget.WIDGETS.layout())


        for w, widget in enumerate(widgets):
            try:
                self.add_widget(widget, w)
            except:
                pass
        self.widgets = widgets






    def add_widget(self,widget,w):
        """Add a filter widget according to the configuration"""

        if  widget['Type'] == "checkableComboBox":
            widget['run'] = QgsCheckableComboBox()
            widget['choice'] = QRadioButton()

            self.populate.populateCheckableComboBoxWidget(widget)

        elif  widget['Type'] == "searchComboBox":

            widget['run'] = QgsFeatureListComboBox()
            widget['choice'] = QRadioButton()

            self.populate.populateSearchComboBoxWidget(widget)

        elif  widget['Type'] == "expressionWidget":
            widget['run'] = QgsFieldExpressionWidget()
            widget['choice'] = QRadioButton()
            self.populate.populateExpressionWidget(widget)

        layout_widget = QGridLayout()
        layout_widget.addWidget(widget['choice'], 0,0)
        layout_widget.addWidget(widget['run'], 0,1)
        self.dockwidget.WIDGETS.layout().addLayout(layout_widget, w, 0)

    def remove_widget(self, layout,w ):
        """Remove a filter widget according to the configuration"""

        for i in reversed(range(layout.count())):


            item = layout.itemAt(i)

            # remove it from the layout list
            #layout.removeWidget(widgetToRemove)
            # remove it from the gui


            if item is not None:
                widget = item.widget()


                result = widget.close()

                widget.setParent(None)


                self.layout.removeItem(item)





class FilterEngineTask(QgsTask):
    """Main QgsTask class which filter and unfilter data"""

    def __init__(self, description, dockwidget, action, current_index, managerWidgets):

        QgsTask.__init__(self, description,QgsTask.CanCancel)

        self.exception = None
        self.dockwidget = dockwidget
        self.action = action
        self.current_index = current_index
        self.populate = populateData(self.dockwidget)
        self.managerWidgets = managerWidgets
        self.filter_from = 0
        
        print(self.current_index)



    def run(self):
        """Main function that run the right method from init parameters"""





        """We split the selected layers to be filtered in two categories sql and others"""
        self.layers = {}
        self.layers['ogr'] = []
        self.layers['sqlite'] = []
        self.layers['postgresql'] = []

        for item in selected_layers_data:

            layers =  PROJECT.mapLayersByName(item)
            for layer in layers:
                if layer.isSpatial():
                    if layer.providerType() == 'ogr':
                        capabilities = layer.capabilitiesString().split(', ')
                        if 'Transactions' in capabilities:
                            self.layers['sqlite'].append(layer)
                        else:
                            self.layers['ogr'].append(layer)

                    elif layer.providerType() == 'postgres':
                        self.layers['postgresql'].append(layer)

                    else:
                        capabilities = layer.capabilitiesString().split(', ')
                        if 'Transactions' in capabilities:
                            self.layers['sqlite'].append(layer)
                        else:
                            self.layers['ogr'].append(layer)





        if self.action == 'start':
            """We will filter layers"""


            


            if self.current_index == 0:
                """If user is on basic tab we launch the basic filtering"""
                self.filter_basic()

            elif self.current_index == 1 and avance == 0:
                """If user is on widget tab and the advanced checkbox is not checked then we launch the widget filtering"""
                self.filter_widget()


            elif avance == 2:
                """If user is on widget tab and the advanced checkbox is checked then we launch the advanced filtering"""

                from_layer = PROJECT.mapLayersByName(layer_name)[0]

                status = self.filter_advanced(expression, from_layer, None)
                #self.managerWidgets.update_widgets()
                if not status:
                    return False

        elif self.action == 'end':
            """We will unfilter the layers"""

            for layer in self.layers['sql']:
                if isinstance(layer, QgsVectorLayer):

                    layer.setSubsetString('')
            for layer in self.layers['shape']:
                if isinstance(layer, QgsVectorLayer):

                    layer.setSubsetString('')


        elif self.action == 'export':
            """We will export layers"""

            status = self.export_to_package()
            return status


        return True
        #except Exception as e:
            #self.exception = e
            #print(self.exception)
            #return False


    def export_to_package(self):
        """Main function to export the selected layers to the right format with their associated styles"""

        format = self.dockwidget.comboBox_export_type.currentText()
        output = {}
        name = str(self.dockwidget.lineEdit_export.text()) if self.dockwidget.lineEdit_export.text() != '' else 'output'
        crs = self.dockwidget.mQgsProjectionSelectionWidget.crs()
        if format == 'GeoPackage':
            alg_parameters_export = {
                'LAYERS': [PROJECT.mapLayersByName(layer)[0] for layer in self.dockwidget.comboBox_select_layers.checkedItems()],
                'OVERWRITE':True,
                'SAVE_STYLES':True,
                'OUTPUT':PATH_ABSOLUTE_PROJECT + '\{name}.{format}'.format(name=name,format='gpkg')

                }
            print(PATH_ABSOLUTE_PROJECT + '\{name}.{format}'.format(name=name,format='gpkg'))
            output = processing.run("qgis:package", alg_parameters_export)

        else:
            if not os.path.isdir(PATH_ABSOLUTE_PROJECT + os.sep + name):
                os.mkdir(PATH_ABSOLUTE_PROJECT + os.sep + name)

            for layer in self.dockwidget.comboBox_select_layers.checkedItems():
                if self.isCanceled():
                    print('Cancel')
                    return False
                QgsVectorFileWriter.writeAsVectorFormat(PROJECT.mapLayersByName(layer)[0], PATH_ABSOLUTE_PROJECT + os.sep + name + os.sep + PROJECT.mapLayersByName(layer)[0].name(), "UTF-8", crs, format)
                if format != 'XLSX':
                    PROJECT.mapLayersByName(layer)[0].saveNamedStyle(PATH_ABSOLUTE_PROJECT + os.sep + name + os.sep + PROJECT.mapLayersByName(layer)[0].name() + '.qml')

        return True


    def filter_expression(self, layer):
        """Manage the creation of the origin filtering expression"""
        try:
            for feat in layer.getFeatures():
                first_feat = feat
                break

            exp = QgsExpression(self.expression)
            context = QgsExpressionContext()
            context.setFeature(first_feat)
            context.setFields(layer.fields())
            print(exp.evaluate(context), exp.evalErrorString())
        except:
            pass
        old_subset = layer.subsetString()

        self.from_operator = self.dockwidget.comboBox_filter_add.currentText()
        print('Going sql')
        self.filter =  self.expression

        if self.filter_add == 2:
            """If we add the current expression to the previous expression"""
            filtered = layer.setSubsetString('(' + old_subset + ') ' + self.from_operator + ' ' + self.filter)
            print('(' + old_subset + ') ' + self.from_operator + ' ' + self.filter)
        else:
            filtered = layer.setSubsetString(self.filter)

        if not filtered:
            print('Going select ids')

            features_list = []
            layer.selectByExpression(self.expression)
            field_idx = layer.fields().indexFromName(self.fields_id[layer.id()])
            if field_idx != -1:
                for feat in layer.selectedFeatures():
                    if self.isCanceled():
                        print('Cancel')
                        return False
                    features_list.append(feat[self.fields_id[layer.id()]])
                string_ints = [str(int) for int in features_list]

                if len(string_ints) > 0:
                    self.filter = '"{}" IN (\''.format(self.fields_id[layer.id()]) + '\',\''.join(string_ints)  + '\')'
                elif len(string_ints) == 0:
                    self.filter = '"{}" is null'.format(self.fields_id[layer.id()])


                if self.filter_add == 2:
                    layer.setSubsetString('(' + old_subset + ') ' + self.from_operator + ' ' + self.filter)
                    print('(' + old_subset + ') ' + self.from_operator + ' ' + self.filter)
                else:
                    layer.setSubsetString(self.filter)


    def filter_advanced(self, expression, from_layer, field_name):
        """Manage the advanced filtering"""


        if 'dbname' in from_layer.dataProvider().dataSourceUri():
            layer_type = 'sql'
        else:
            layer_type = 'shape'

        self.expression = expression



        """We create the origin expression"""
        if self.filter_multi == 2:
            for layer in self.layers['sql']:

                self.filter_expression(layer)

            for layer in self.layers['shape']:

                self.filter_expression(layer)


        else:
            self.filter_expression(from_layer)

        if self.filter_geo == 2:
            """If geospatial filter is activated"""
            self.filter_geospatial(from_layer, self.layers['sql'] + self.layers['shape'])



        if self.filter_from == 2 and field_name is not None:
            """Advanced filter from basic commune filter"""
            if len(self.selected_za_nro_data) > 0:
                from_layer.setSubsetString('(' + self.filter_za_nro[layer_type] + ') AND ' + expression)

            elif len(self.selected_za_zpm_data) > 0:
                from_layer.setSubsetString('(' + self.filter_za_zpm[layer_type] + ') AND ' + expression)

            elif len(self.selected_za_zpa_data) > 0:
                from_layer.setSubsetString('(' + self.filter_za_zpa[layer_type] + ') AND ' + expression)

            else:
                from_layer.setSubsetString(expression)


            idx = from_layer.fields().indexFromName(field_name)
            list_items = []

            selected_items = {}
            selected_items['sql'] = []
            selected_items['shape'] = []

            self.filter_items = {}
            self.filter_items['sql'] = ''
            self.filter_items['shape'] = ''

            for feature in from_layer.getFeatures():
                feature_field = feature.attributes()[idx]
                if feature_field != NULL:
                    if ',' in feature_field:
                        feature_array = feature_field.split(',')
                        for feat_field in feature_array:
                            if feat_field not in list_items:
                                list_items.append(feat_field)

                    else:
                        if feature_field not in list_items:
                            list_items.append(feature_field)


            for item in list_items:
                selected_items['sql'].append('"' + str(field_name) + '" ~ \'' + str(item) + '$\'' + ' OR "' +  str(field_name) + '" ~ \'' + str(item) + ',\'' )
                selected_items['shape'].append('"' + str(field_name) + '" LIKE \'' + str(item) + '\'')

            self.filter_items['sql'] = ' OR '.join(selected_items['sql'])
            self.filter_items['shape'] = ' OR '.join(selected_items['shape'])

            for layer in self.layers['sql']:
                if layer.name() != from_layer.name():
                    field_idx = layer.fields().indexFromName(field_name)
                    if field_idx == -1:
                        print('Le champ ' + field_name + ' non présent dans la couche ' + layer.name())
                    else:
                        layer.setSubsetString(self.filter_items['sql'])

            for layer in self.layers['shape']:
                if layer.name() != from_layer.name():
                    field_idx = layer.fields().indexFromName(field_name)
                    if field_idx == -1:
                        print('Le champ ' + field_name + ' non présent dans la couche ' + layer.name())
                    else:
                        layer.setSubsetString(self.filter_items['shape'])

        return True






    def filter_geospatial(self, from_layer, layers):
        """Filter layers from a prefiltered layer"""

        with_tampon = self.dockwidget.checkBox_tampon.checkState()
        predicats = self.dockwidget.mComboBox_filter_geo.checkedItems()




        if with_tampon == 2:
            distance = float(self.dockwidget.mQgsDoubleSpinBox_tampon.value())
            print(distance)
            outputs = {}
            alg_params_buffer = {
                'DISSOLVE': True,
                'DISTANCE': distance,
                'END_CAP_STYLE': 2,
                'INPUT': from_layer,
                'JOIN_STYLE': 2,
                'MITER_LIMIT': 2,
                'SEGMENTS': 5,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }
            outputs['alg_params_buffer'] = processing.run('qgis:buffer', alg_params_buffer)
            layer_name = from_layer.name()
            from_layer = outputs['alg_params_buffer']['OUTPUT']
            from_layer.setName(layer_name)


        for layer in layers:
            if layer.name() != from_layer.name():
                old_subset = layer.subsetString()
                features_list = []
                alg_params_select = {

                    'INPUT': layer,
                    'INTERSECT': from_layer,
                    'METHOD': 0,
                    'PREDICATE':[int(predicat[0]) for predicat in predicats]
                }
                field_idx = layer.fields().indexFromName(self.fields_id[layer.id()])
                if field_idx != -1:
                    processing.run("qgis:selectbylocation", alg_params_select)
                    for feat in layer.selectedFeatures():
                        if self.isCanceled():
                            return False
                        features_list.append(feat[self.fields_id[layer.id()]])
                    string_ints = [str(int) for int in features_list]

                    if len(string_ints) > 0:
                        self.filter = '"{}" IN (\''.format(self.fields_id[layer.id()]) + '\',\''.join(string_ints)  + '\')'
                    elif len(string_ints) == 0:
                        self.filter = '"{}" is null'.format(self.fields_id[layer.id()])

                    if self.filter_add_multi == 2 and old_subset != self.filter:
                        layer.setSubsetString('(' + old_subset + ') ' + self.multi_operator + ' ' + self.filter)
                        print('(' + old_subset + ') ' + self.multi_operator + ' ' + self.filter)
                    else:
                        layer.setSubsetString(self.filter)
                else:
                    print('Le champ "code_id" non présent dans la couche ' + layer.name())
                layer.removeSelection()


    def filter_widget(self):
        """Manage the widget filtering"""
        for widget in self.managerWidgets.widgets:
            if widget['choice'].isChecked():
                if   widget['Type'] == 'searchComboBox':
                    values = [widget['run'].currentText()]
                    self.expression = '"{field}" in (\'{values}\')'.format(field=widget['Parameters']['field'], values='\',\''.join(values))
                elif  widget['Type'] == 'checkableComboBox':
                    values = widget['run'].checkedItems()
                    self.expression = '"{field}" in (\'{values}\')'.format(field=widget['Parameters']['field'], values='\',\''.join(values))
                elif  widget['Type'] == 'expressionWidget':
                    expression =  widget['run'].currentText()
                    expression = expression.replace("'", "\'")
                    self.expression  = expression



                if self.filter_multi == 2:
                    for layer in self.layers['sql']:

                        self.filter_expression(layer)
                        if (layer.subsetString() == '"{}" is null'.format(self.fields_id[layer.id()]) or layer.featureCount() == 0) and self.filter_geo == 2:
                            layer.setSubsetString('')
                            self.filter_geospatial(PROJECT.mapLayersByName(widget['Parameters']['layer'])[0], [layer])

                    for layer in self.layers['shape']:

                        self.filter_expression(layer)
                        if (layer.subsetString() == '"{}" is null'.format(self.fields_id[layer.id()]) or layer.featureCount() == 0) and self.filter_geo == 2:
                            layer.setSubsetString('')
                            self.filter_geospatial(PROJECT.mapLayersByName(widget['Parameters']['layer'])[0], [layer])


                else:
                    self.filter_expression(PROJECT.mapLayersByName(widget['Parameters']['layer'])[0])
                    if self.filter_geo == 2:
                        self.filter_geospatial(PROJECT.mapLayersByName(widget['Parameters']['layer'])[0], self.layers['sql'] + self.layers['shape'])





                break


    def cancel(self):
        QgsMessageLog.logMessage(
            '"{name}" was canceled'.format(name=self.description()))
        super().cancel()

    def finished(self, result):
        """This function is called automatically when the task is completed and is
        called from the main thread so it is safe to interact with the GUI etc here"""
        if result is False:
            if self.exception is None:
                iface.messageBar().pushMessage('Task was cancelled')
            else:
                iface.messageBar().pushMessage('Errors occured')
                print(self.exception)

        else:
            print('Couches filtrées')


class barProgress:

    def __init__(self):
        self.prog = 0
        self.bar = None
        self.type = type
        iface.messageBar().clearWidgets()
        self.init()
        self.bar.show()

    def init(self):
        self.bar = QProgressBar()
        self.bar.setMaximum(100)
        self.bar.setValue(self.prog)
        iface.mainWindow().statusBar().addWidget(self.bar)

    def show(self):
        self.bar.show()


    def update(self, prog):
        self.bar.setValue(prog)

    def hide(self):
        self.bar.hide()

class msgProgress:

    def __init__(self):
        self.messageBar = iface.messageBar().createMessage('Doing something time consuming...')
        self.progressBar = QProgressBar()
        self.progressBar.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
        self.cancelButton = QPushButton()
        self.cancelButton.setText('Cancel')
        self.messageBar.layout().addWidget(self.progressBar)
        self.messageBar.layout().addWidget(self.cancelButton)
        iface.messageBar().pushWidget(self.messageBar, Qgis.Info)


    def update(self, prog):
        self.progressBar.setValue(prog)

    def reset(self):
        self.progressBar.setValue(0)

    def setText(self, text):
        self.messageBar.setText(text)




def zoom_to_features(layer, t0):
    end = time.time() - t0
    print("DONE" + " IN " + str(end) + " s.")
    canvas = iface.mapCanvas()
    canvas.setExtent(layer.extent())
    canvas.refresh()





class populateData:
    """Class managing the comboboxes data population"""

    def __init__(self, dockwidget):
        self.dockwidget = dockwidget
        self.exception = None


    def checkState(self, combobox):


        print(combobox.itemCheckState(0))
        if combobox.itemCheckState(0) == 2:
            combobox.selectAllOptions()
        elif combobox.itemCheckState(0) == 0:
            combobox.deselectAllOptions()


    def populate_predicat(self):

        predicats = ['0:intersecte','1:contient','2:est disjoint','3:égal','4:touche','5:chevauche','6:est à l\'intérieur','7:croise']


        self.dockwidget.mComboBox_filtering_geometric_predicates.clear()
        self.dockwidget.mComboBox_filtering_geometric_predicates.addItems(predicats)

    def populate_layers(self):

        layers = PROJECT.mapLayers().values()



        list_layers = []
        for layer in layers:
            if isinstance(layer, QgsVectorLayer):
                layer_name = layer.name()
                list_layers.append(layer_name)


        self.dockwidget.comboBox_filtering_layers_to_filter.clear()
        self.dockwidget.comboBox_filtering_layers_to_filter.addItems(list_layers)
        self.dockwidget.comboBox_filtering_layers_to_filter.selectAllOptions()
        
        self.dockwidget.comboBox_exporting_layers.clear()
        self.dockwidget.comboBox_exporting_layers.addItems(list_layers)
        self.dockwidget.comboBox_exporting_layers.selectAllOptions()



    def populateCheckableComboBoxWidget(self, widget):

        print('populate checkableComboBox')
        list = []

        layer = PROJECT.mapLayersByName(widget['Parameters']['layer'])[0]
        idx = layer.fields().indexFromName(widget['Parameters']['field'])

        for feature in layer.getFeatures():

            if feature.attributes()[idx] not in list:
                list.append(str(feature.attributes()[idx]))


        list = sorted(list)
        widget['run'].clear()
        widget['run'].addItems(list)
        return widget


    def populateSearchComboBoxWidget(self, widget):

        print('populate searchComboBox')
        layer = PROJECT.mapLayersByName(widget['Parameters']['layer'])[0]
        #widget['run'].clear()
        widget['run'].setSourceLayer(layer)
        widget['run'].setIdentifierField(widget['Parameters']['id'])
        widget['run'].setDisplayExpression(widget['Parameters']['field'])
        widget['run'].setFilterExpression(layer.subsetString())
        widget['run'].updateMicroFocus()
        return widget


    def populateExpressionWidget(self, widget):
        print('populate expressionWidget')
        layer = PROJECT.mapLayersByName(widget['Parameters']['layer'])[0]
        widget['run'].setLayer(layer)

        return widget
