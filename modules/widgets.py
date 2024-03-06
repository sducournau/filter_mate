from qgis.PyQt import QtGui, QtWidgets, QtCore, uic
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from PyQt5.QtWidgets import QSizePolicy
from qgis.core import *
from qgis.gui import *
from qgis.utils import iface
from qgis.PyQt.QtWidgets import QApplication, QVBoxLayout
from functools import partial
import json

class PopulateListEngineTask(QgsTask):
    """Main QgsTask class which filter and unfilter data"""

    def __init__(self, description, parent, action, silent_flag):

        QgsTask.__init__(self, description, QgsTask.CanCancel)

        self.exception = None
        self.sub_action = self.description()
        self.action = action

        self.parent = parent

        self.silent_flag = silent_flag
        self.layer = self.parent.layer
        self.identifier_field_name = self.parent.list_widgets[self.layer.id()].getIdentifierFieldName()
        self.display_expression = self.parent.list_widgets[self.layer.id()].getDisplayExpression()
        self.is_field_flag = self.parent.list_widgets[self.layer.id()].getExpressionFieldFlag()


    def run(self):
        """Main function that run the right method from init parameters"""
        try:
            if self.action == 'buildFeaturesList':
                self.buildFeaturesList()
            elif self.action == 'loadFeaturesList':
                self.loadFeaturesList()
            elif self.action == 'selectAllFeatures':
                self.selectAllFeatures()
            elif self.action == 'deselectAllFeatures':
                self.deselectAllFeatures()
            elif self.action == 'filterFeatures':
                self.filterFeatures()   
            elif self.action == 'updateFeatures':
                self.updateFeatures()

            return True
        
        except Exception as e:
            self.exception = e
            print(self.exception)
            return False

    def get_task_action_and_layer(self):
        return self.action, self.layer
    
    def buildFeaturesList(self, has_limit=True, filter_txt_splitted=None):

        features_list = []

        limit = 0
        layer_features_source = None
        total_features_list_count = 0
        filter_expression_request = QgsFeatureRequest()

        subset_string_init = self.layer.subsetString()
        if subset_string_init != '':
            self.layer.setSubsetString('')

        data_provider_layer = self.layer.dataProvider()
        if data_provider_layer:
            total_features_list_count = data_provider_layer.featureCount()
            layer_features_source = data_provider_layer.featureSource()

        if subset_string_init != '':
            self.layer.setSubsetString(subset_string_init)

        if self.parent.list_widgets[self.layer.id()].getTotalFeaturesListCount() == 0 and total_features_list_count > 0:
            self.parent.list_widgets[self.layer.id()].setTotalFeaturesListCount(total_features_list_count)

        if layer_features_source != None and has_limit is True:
            limit = self.parent.list_widgets[self.layer.id()].getLimit()
            
        
        if layer_features_source != None:
            if self.parent.list_widgets[self.layer.id()].getFilterExpression() != '':
                filter_expression = self.parent.list_widgets[self.layer.id()].getFilterExpression()
                if QgsExpression(filter_expression).isValid():

                    if filter_txt_splitted != None:
                        filter_txt_splitted_final = []
                        for filter_txt in filter_txt_splitted:
                            filter_txt_splitted_final.append("""{display_expression} *~ '{filter_txt}'""".format(display_expression=self.display_expression,
                                                                                                                filter_txt=filter_txt.replace('é','?').replace('è','?').replace('â','?').replace('ô','?')))
                                              
                        filter_txt_string_final = ' OR '.join(filter_txt_splitted_final)
                        filter_expression = filter_expression + ' AND ( {filter_txt_string_final} )'.format(filter_txt_string_final=filter_txt_string_final)
                        filter_expression_request = QgsFeatureRequest(QgsExpression(filter_expression))
                    else: 
                        filter_expression_request = QgsFeatureRequest(QgsExpression(filter_expression))

                    if limit > 0:
                        filter_expression_request.setLimit(limit)

                    total_count = sum(1 for _ in layer_features_source.getFeatures(filter_expression_request))

                    if self.is_field_flag is True:
                        for index, feature in enumerate(layer_features_source.getFeatures(filter_expression_request)):
                            arr = [feature[self.display_expression], feature[self.identifier_field_name]]
                            features_list.append(arr)
                            self.setProgress((index/total_count)*100)
                    else:
                        display_expression = QgsExpression(self.display_expression)

                        if display_expression.isValid():
                            
                            context = QgsExpressionContext()
                            scope = QgsExpressionContextScope()
                            context.appendScope(scope)


                            for index, feature in enumerate(layer_features_source.getFeatures(filter_expression_request)):
                                scope.setFeature(feature)
                                result = display_expression.evaluate(context)
                                if result:
                                    arr = [result, feature[self.identifier_field_name]]
                                    features_list.append(arr)
                                    self.setProgress((index/total_count)*100)


            
            else:

                if filter_txt_splitted != None:
                    filter_txt_splitted_final = []
                    for filter_txt in filter_txt_splitted:
                        filter_txt_splitted_final.append("""{display_expression} *~ '{filter_txt}'""".format(display_expression=self.display_expression,
                                                                                                            filter_txt=filter_txt.replace('é','?').replace('è','?').replace('â','?').replace('ô','?')))
                                            
                    filter_txt_string_final = ' OR '.join(filter_txt_splitted_final)
                    filter_expression_request = QgsFeatureRequest(QgsExpression(filter_txt_string_final))

                if limit > 0:
                    filter_expression_request.setLimit(limit)

                    
                total_count = sum(1 for _ in layer_features_source.getFeatures(filter_expression_request))

                if self.is_field_flag is True:
                    for index, feature in enumerate(layer_features_source.getFeatures(filter_expression_request)):
                        arr = [feature[self.display_expression], feature[self.identifier_field_name]]
                        features_list.append(arr)
                        self.setProgress((index/total_count)*100)
                else:
                    display_expression = QgsExpression(self.display_expression)

                    if display_expression.isValid():
                        
                        context = QgsExpressionContext()
                        scope = QgsExpressionContextScope()
                        context.appendScope(scope)


                        for index, feature in enumerate(layer_features_source.getFeatures(filter_expression_request)):
                            scope.setFeature(feature)
                            result = display_expression.evaluate(context)
                            if result:
                                arr = [result, feature[self.identifier_field_name]]
                                features_list.append(arr)
                                self.setProgress((index/total_count)*100)

            nonSubset_features_list = [feature[self.identifier_field_name] for feature in self.layer.getFeatures()]
            self.parent.list_widgets[self.layer.id()].setFeaturesList(features_list)
            self.parent.list_widgets[self.layer.id()].sortFeaturesListByDisplayExpression(nonSubset_features_list)


    def loadFeaturesList(self, new_list=True):
        current_selected_features_list = [feature[1] for feature in self.parent.list_widgets[self.layer.id()].getSelectedFeaturesList()]
        nonSubset_features_list = [feature[self.identifier_field_name] for feature in self.layer.getFeatures()]
        
        if new_list is True:
            self.parent.list_widgets[self.layer.id()].clear()

        filter_text = self.parent.list_widgets[self.layer.id()].getFilterText()
        if filter_text != '':
            self.parent.filter_le.setText(filter_text)

        list_to_load = self.parent.list_widgets[self.layer.id()].getFeaturesList()

        total_count = len(list_to_load)
        for index, it in enumerate(list_to_load):
            lwi = QListWidgetItem(str(it[0]))
            lwi.setData(0,str(it[0]))
            lwi.setData(3,it[1])
            lwi.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            if it[1] in current_selected_features_list:
                lwi.setCheckState(Qt.Checked)
                if it[1] in nonSubset_features_list:
                    lwi.setData(6,self.parent.font_by_state['checked'][0])
                    lwi.setData(9,QBrush(self.parent.font_by_state['checked'][1]))
                    lwi.setData(4,"True")
                else:
                    lwi.setData(6,self.parent.font_by_state['checkedFiltered'][0])
                    lwi.setData(9,QBrush(self.parent.font_by_state['checkedFiltered'][1]))
                    lwi.setData(4,"False")
            else:
                lwi.setCheckState(Qt.Unchecked)
                if it[1] in nonSubset_features_list:
                    lwi.setData(6,self.parent.font_by_state['unChecked'][0])
                    lwi.setData(9,QBrush(self.parent.font_by_state['unChecked'][1]))
                    lwi.setData(4,"True")
                else:
                    lwi.setData(6,self.parent.font_by_state['unCheckedFiltered'][0])
                    lwi.setData(9,QBrush(self.parent.font_by_state['unCheckedFiltered'][1]))
                    lwi.setData(4,"False")
            self.parent.list_widgets[self.layer.id()].addItem(lwi)
            self.setProgress((index/total_count)*100)


        self.updateFeatures()

            
    def filterFeatures(self):
        total_count = self.parent.list_widgets[self.layer.id()].count()
        filter_txt_splitted = self.parent.filter_txt.lower().strip().split(" ")

        self.parent.list_widgets[self.layer.id()].setFilterText(self.parent.filter_txt)

        if self.parent.list_widgets[self.layer.id()].getTotalFeaturesListCount() > total_count:
            self.buildFeaturesList(False, filter_txt_splitted)
            self.loadFeaturesList(True)

        else:
            filter_txt_splitted = [item.replace('é','e').replace('è','e').replace('â','a').replace('ô','o') for item in filter_txt_splitted]
            for index, it in enumerate(range(self.parent.list_widgets[self.layer.id()].count())):
                item = self.parent.list_widgets[self.layer.id()].item(it)
                string_value = item.text().lower().replace('é','e').replace('è','e').replace('â','a').replace('ô','o')
                filter = all(x not in string_value for x in filter_txt_splitted)
                self.parent.list_widgets[self.layer.id()].setRowHidden(it, filter)
                self.setProgress((index/total_count)*100)

        visible_features_list = []
        for index, it in enumerate(range(self.parent.list_widgets[self.layer.id()].count())):
            item = self.parent.list_widgets[self.layer.id()].item(it)
            if not item.isHidden():
                visible_features_list.append([item.data(0), item.data(3), bool(item.data(4))])

        self.parent.filteredCheckedItemListEvent(visible_features_list, True)


    def selectAllFeatures(self):


        if self.sub_action == 'Select All':

            total_count = self.parent.list_widgets[self.layer.id()].count()
            nonSubset_features_list = [feature[self.identifier_field_name] for feature in self.layer.getFeatures()]

            for index, it in enumerate(range(self.parent.list_widgets[self.layer.id()].count())):
                item = self.parent.list_widgets[self.layer.id()].item(it)
                if not item.isHidden():
                    item.setCheckState(Qt.Checked)
                    item.setData(6,self.parent.font_by_state['checked'][0])
                    item.setData(9,QBrush(self.parent.font_by_state['checked'][1]))
                    item.setData(4,"True")
                self.setProgress((index/total_count)*100)

        
        elif self.sub_action == 'Select All (non subset)':

            total_count = self.parent.list_widgets[self.layer.id()].count()
            nonSubset_features_list = [feature[self.identifier_field_name] for feature in self.layer.getFeatures()]
            total_count = total_count - len([feature[self.identifier_field_name] for feature in self.layer.getFeatures()])

            for index, it in enumerate(range(self.parent.list_widgets[self.layer.id()].count())):
                item = self.parent.list_widgets[self.layer.id()].item(it)
                if not item.isHidden():
                    if item.data(3) not in nonSubset_features_list:
                        item.setCheckState(Qt.Checked)
                        item.setData(6,self.parent.font_by_state['checkedFiltered'][0])
                        item.setData(9,QBrush(self.parent.font_by_state['checkedFiltered'][1]))
                        item.setData(4,"False")
                self.setProgress((index/total_count)*100)
        

        elif self.sub_action == 'Select All (subset)':

            nonSubset_features_list = [feature[self.identifier_field_name] for feature in self.layer.getFeatures()]
            total_count = len([feature[self.identifier_field_name] for feature in self.layer.getFeatures()])

            for index, it in enumerate(range(self.parent.list_widgets[self.layer.id()].count())):
                item = self.parent.list_widgets[self.layer.id()].item(it)
                if not item.isHidden():
                    if item.data(3) in nonSubset_features_list:
                        item.setCheckState(Qt.Checked)
                        item.setData(6,self.parent.font_by_state['checked'][0])
                        item.setData(9,QBrush(self.parent.font_by_state['checked'][1]))
                        item.setData(4,"True")
                self.setProgress((index/total_count)*100)

        self.updateFeatures()


    def deselectAllFeatures(self):

        if self.sub_action == 'De-select All':

            total_count = self.parent.list_widgets[self.layer.id()].count()
            nonSubset_features_list = [feature[self.identifier_field_name] for feature in self.layer.getFeatures()]

            for index, it in enumerate(range(self.parent.list_widgets[self.layer.id()].count())):
                item = self.parent.list_widgets[self.layer.id()].item(it)
                if not item.isHidden():
                    item.setCheckState(Qt.Unchecked)
                    item.setData(6,self.parent.font_by_state['unChecked'][0])
                    item.setData(9,QBrush(self.parent.font_by_state['unChecked'][1]))
                    item.setData(4,"True")
                self.setProgress((index/total_count)*100)

        elif self.sub_action == 'De-select All (non subset)':

            total_count = self.parent.list_widgets[self.layer.id()].count()
            nonSubset_features_list = [feature[self.identifier_field_name] for feature in self.layer.getFeatures()]
            total_count = total_count - len([feature[self.identifier_field_name] for feature in self.layer.getFeatures()])

            for index, it in enumerate(range(self.parent.list_widgets[self.layer.id()].count())):
                item = self.parent.list_widgets[self.layer.id()].item(it)
                if not item.isHidden():
                    if item.data(3) not in nonSubset_features_list:
                        item.setCheckState(Qt.Unchecked)
                        item.setData(6,self.parent.font_by_state['unCheckedFiltered'][0])
                        item.setData(9,QBrush(self.parent.font_by_state['unCheckedFiltered'][1]))
                        item.setData(4,"False")
                self.setProgress((index/total_count)*100)


        elif self.sub_action == 'De-select All (subset)':

            nonSubset_features_list = [feature[self.identifier_field_name] for feature in self.layer.getFeatures()]
            total_count = len([feature[self.identifier_field_name] for feature in self.layer.getFeatures()])

            for index, it in enumerate(range(self.parent.list_widgets[self.layer.id()].count())):
                item = self.parent.list_widgets[self.layer.id()].item(it)
                if not item.isHidden():
                    if item.data(3) in nonSubset_features_list:
                        item.setCheckState(Qt.Unchecked)
                        item.setData(6,self.parent.font_by_state['unCheckedFiltered'][0])
                        item.setData(9,QBrush(self.parent.font_by_state['unCheckedFiltered'][1]))
                        item.setData(4,"False")
                self.setProgress((index/total_count)*100)

        self.updateFeatures()

    
    def updateFeatures(self):

        selection_data = []
        visible_data = []
        total_count = self.parent.list_widgets[self.layer.id()].count()
        for index, it in enumerate(range(self.parent.list_widgets[self.layer.id()].count())):
            item = self.parent.list_widgets[self.layer.id()].item(it)
            if item.checkState() == Qt.Checked:
                selection_data.append([item.data(0), item.data(3), bool(item.data(4))])
            visible_data.append([item.data(0), item.data(3), bool(item.data(4))])
            self.setProgress((index/total_count)*100)
        selection_data.sort(key=lambda k: k[0])
        self.parent.items_le.setText(', '.join([data[0] for data in selection_data]))
        self.parent.list_widgets[self.layer.id()].setSelectedFeaturesList(selection_data)
        self.parent.list_widgets[self.layer.id()].setVisibleFeaturesList(visible_data)
        self.parent.updatedCheckedItemListEvent(selection_data, True)
        
    
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


class QgsCheckableComboBoxFeaturesListPickerWidget(QWidget):
    '''
    Copy and paste this class into your PyQGIS project/ plugin
    '''
    updatingCheckedItemList = pyqtSignal(list, bool)
    filteringCheckedItemList = pyqtSignal()
    
    def __init__(self, config_data, parent=None):
        self.parent = parent
        QDialog.__init__(self)


        self.config_data = config_data
        self.setMinimumWidth(30)
        self.setMaximumWidth(16777215)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.setCursor(Qt.PointingHandCursor)

        font = QFont("Segoe UI", 8)
        self.setFont(font)


        self.layout = QVBoxLayout(self)
        self.filter_le = QLineEdit(self)
        self.filter_le.setPlaceholderText('Type to filter...')
        self.items_le = QLineEdit(self)
        self.items_le.setReadOnly(True)

        self.layout.addWidget(self.filter_le)
        self.layout.addWidget(self.items_le)




        self.context_menu = QMenu(self)
        self.action_check_all = QAction('Select All', self)
        self.action_check_all.triggered.connect(lambda state, x='Select All': self.select_all(x))
        self.action_check_all_non_subset = QAction('Select All (non subset)', self)
        self.action_check_all_non_subset.triggered.connect(lambda state, x='Select All (non subset)': self.select_all(x))
        self.action_check_all_subset = QAction('Select All (subset)', self)
        self.action_check_all_subset.triggered.connect(lambda state, x='Select All (subset)': self.select_all(x))
        self.action_uncheck_all = QAction('De-select All', self)
        self.action_uncheck_all.triggered.connect(lambda state, x='De-select All': self.deselect_all(x))
        self.action_uncheck_all_non_subset = QAction('De-select All (non subset)', self)
        self.action_uncheck_all_non_subset.triggered.connect(lambda state, x='De-select All (non subset)': self.deselect_all(x))
        self.action_uncheck_all_subset = QAction('De-select All (subset)', self)
        self.action_uncheck_all_subset.triggered.connect(lambda state, x='De-select All (subset)': self.deselect_all(x))

        self.context_menu.addAction(self.action_check_all)
        self.context_menu.addAction(self.action_check_all_non_subset)
        self.context_menu.addAction(self.action_check_all_subset)
        self.context_menu.addSeparator()
        self.context_menu.addAction(self.action_uncheck_all)
        self.context_menu.addAction(self.action_uncheck_all_non_subset)
        self.context_menu.addAction(self.action_uncheck_all_subset)

        self.font_by_state = {'unChecked':(QFont("Segoe UI", 8, QFont.Medium),(QColor(self.config_data["APP"]["DOCKWIDGET"]["COLORS"]["FONT"][0]))),
                              'checked':(QFont("Segoe UI", 8, QFont.Bold),(QColor(self.config_data["APP"]["DOCKWIDGET"]["COLORS"]["FONT"][0]))),
                              'unCheckedFiltered':(QFont("Segoe UI", 8, QFont.Medium),(QColor(self.config_data["APP"]["DOCKWIDGET"]["COLORS"]["FONT"][2]))),
                              'checkedFiltered':(QFont("Segoe UI", 8, QFont.Bold),(QColor(self.config_data["APP"]["DOCKWIDGET"]["COLORS"]["FONT"][2])))}


        self.list_widgets = {}

        self.tasks = {}


        self.tasks['buildFeaturesList'] = {}
        self.tasks['updateFeaturesList'] = {}
        self.tasks['loadFeaturesList'] = {}
        self.tasks['selectAllFeatures'] = {}
        self.tasks['deselectAllFeatures'] = {}
        self.tasks['filterFeatures'] = {}
        self.tasks['updateFeatures'] = {}

        self.last_layer = None
        self.layer = None
        self.is_field_flag = None

    def checkedItems(self):
        selection = []
        for i in range(self.list_widgets[self.layer.id()].count()):
            item = self.list_widgets[self.layer.id()].item(i)
            if item.checkState() == Qt.Checked:
                selection.append([item.data(0), item.data(3),  item.data(6), item.data(9)])
        selection.sort(key=lambda k: k[0])
        return selection

    def displayExpression(self):
        if self.layer != None:
            return self.list_widgets[self.layer.id()].getDisplayExpression()
        else:
            return False
      
    def currentLayer(self):
        if self.layer != None:
            return self.layer
        else:
            return False
    
    def currentSelectedFeatures(self):
        if self.layer != None:
            current_selected_features = self.list_widgets[self.layer.id()].getSelectedFeaturesList()
            return current_selected_features if len(current_selected_features) > 0 else False
        else:
            return False
        
    def currentVisibleFeatures(self):
        if self.layer != None:
            visible_features_list = self.list_widgets[self.layer.id()].getVisibleFeaturesList()
            return visible_features_list if len(visible_features_list) > 0 else False
        else:
            return False
        
    def setLayer(self, layer, layer_props):

        try:

            if layer != None:
                if self.layer != None:
                    if self.layer.id() not in self.list_widgets:
                        self.manage_list_widgets(layer_props)
                    self.filter_le.clear()
                    self.items_le.clear()
                    
                self.layer = layer

                if self.list_widgets[self.layer.id()].getIdentifierFieldName() != layer_props["infos"]["primary_key_name"]:
                    self.list_widgets[self.layer.id()].setIdentifierFieldName(layer_props["infos"]["primary_key_name"])

                self.manage_list_widgets(layer_props)

                self.filter_le.setText(self.list_widgets[self.layer.id()].getFilterText())

                if self.list_widgets[self.layer.id()].getDisplayExpression() != layer_props["exploring"]["multiple_selection_expression"]:
                    self.setDisplayExpression(layer_props["exploring"]["multiple_selection_expression"])
                else:
                    description = 'Loading features'
                    action = 'loadFeaturesList'
                    self.build_task(description, action, True)
                    self.launch_task(action)

        except:
            try:
                self.filter_le.clear()
                self.items_le.clear()
            except:
                pass
    

    def setFilterExpression(self, filter_expression, layer_props):
        if self.layer != None:
            if self.layer.id() not in self.list_widgets:
                self.manage_list_widgets(layer_props)
            if self.layer.id() in self.list_widgets:  
                if filter_expression != self.list_widgets[self.layer.id()].getFilterExpression():
                    if QgsExpression(filter_expression).isField() is False:
                        self.list_widgets[self.layer.id()].setFilterExpression(filter_expression)
                        expression = self.list_widgets[self.layer.id()].getDisplayExpression()
                        self.setDisplayExpression(expression)


    def setDisplayExpression(self, expression):
        
        if self.layer != None:
            self.filter_le.clear()
            self.items_le.clear()
        
            if QgsExpression(expression).isField():
                working_expression = expression.replace('"', '')
                self.list_widgets[self.layer.id()].setExpressionFieldFlag(True)
            else:
                working_expression = expression
                self.list_widgets[self.layer.id()].setExpressionFieldFlag(False)

            self.list_widgets[self.layer.id()].setDisplayExpression(working_expression)

            sub_description = 'Building features list'
            sub_action = 'buildFeaturesList'

            self.build_task(sub_description, sub_action)

            description = 'Loading features'
            action = 'loadFeaturesList'
            self.build_task(description, action)

            self.tasks['loadFeaturesList'][self.layer.id()].addSubTask(self.tasks[sub_action][self.layer.id()], [], QgsTask.ParentDependsOnSubTask)

            self.launch_task('loadFeaturesList')
                
        

    def eventFilter(self, obj, event):

        if event.type() == QEvent.MouseButtonPress and obj == self.list_widgets[self.layer.id()].viewport():
            identifier_field_name = self.list_widgets[self.layer.id()].getIdentifierFieldName()
            nonSubset_features_list = [feature[identifier_field_name] for feature in self.layer.getFeatures()]
            if event.button() == Qt.LeftButton:
                clicked_item = self.list_widgets[self.layer.id()].itemAt(event.pos())
                if clicked_item != None:
                    id_item = clicked_item.data(3)
                    if clicked_item.checkState() == Qt.Checked:
                        clicked_item.setCheckState(Qt.Unchecked)
                        if id_item in nonSubset_features_list:
                            clicked_item.setData(6,self.font_by_state['unChecked'][0])
                            clicked_item.setData(9,QBrush(self.font_by_state['unChecked'][1]))
                            clicked_item.setData(4,"True")
                        else:
                            clicked_item.setData(6,self.font_by_state['unCheckedFiltered'][0])
                            clicked_item.setData(9,QBrush(self.font_by_state['unCheckedFiltered'][1]))
                            clicked_item.setData(4,"False")

                    else:
                        clicked_item.setCheckState(Qt.Checked)
                        if id_item in nonSubset_features_list:
                            clicked_item.setData(6,self.font_by_state['checked'][0])
                            clicked_item.setData(9,QBrush(self.font_by_state['checked'][1]))
                            clicked_item.setData(4,"True")
                        else:   
                            clicked_item.setData(6,self.font_by_state['checkedFiltered'][0])
                            clicked_item.setData(9,QBrush(self.font_by_state['checkedFiltered'][1]))
                            clicked_item.setData(4,"False")
                        
                description = 'Selecting feature'
                action = 'updateFeatures'
                self.build_task(description, action, True)
                self.launch_task(action)

            elif event.button() == Qt.RightButton:
                self.context_menu.exec(QCursor.pos())
            return True
        return False


    def connect_filter_lineEdit(self):

        if self.layer != None:
            if self.layer.id() in self.list_widgets:
                if self.list_widgets[self.layer.id()].getTotalFeaturesListCount() == self.list_widgets[self.layer.id()].count():
                    try:
                        self.filter_le.editingFinished.disconnect()
                    except:
                        pass
                    self.filter_le.textChanged.connect(self.filter_items)
                else:
                    try:
                        self.filter_le.textChanged.disconnect()
                    except:
                        pass
                    self.filter_le.editingFinished.connect(self.filter_items)



    def manage_list_widgets(self, layer_props):
        for key in self.list_widgets.keys():
            self.list_widgets[key].setVisible(False)

        if self.layer.id() in self.list_widgets:
            self.list_widgets[self.layer.id()].setVisible(True)
        else:
            self.add_list_widget(layer_props)


    def remove_list_widget(self, layer_id):
        if layer_id in self.list_widgets:
            for task in self.tasks:
                try:
                    del self.tasks[task][layer_id]
                except:
                    pass
            try:
                del self.list_widgets[layer_id]
            except:
                pass

    def reset(self):
        self.layer = None
        self.tasks = {}
        self.tasks['buildFeaturesList'] = {}
        self.tasks['updateFeaturesList'] = {}
        self.tasks['loadFeaturesList'] = {}
        self.tasks['selectAllFeatures'] = {}
        self.tasks['deselectAllFeatures'] = {}
        self.tasks['filterFeatures'] = {}
        self.tasks['updateFeatures'] = {}
        for i in range(self.layout.count()):
            item = self.layout.itemAt(i)
            widget = item.widget()       
            if widget:
                try:
                    widget.close()
                except:
                    pass

        self.list_widgets = {}


    def add_list_widget(self, layer_props):
        self.list_widgets[self.layer.id()] = ListWidgetWrapper(layer_props["infos"]["primary_key_name"], layer_props["infos"]["primary_key_is_numeric"], self)
        self.list_widgets[self.layer.id()].viewport().installEventFilter(self)
        self.layout.addWidget(self.list_widgets[self.layer.id()])




    def select_all(self, x):
        action = 'selectAllFeatures'
        self.build_task(x, action)
        self.launch_task(action)

    def deselect_all(self, x):
        action = 'deselectAllFeatures'
        self.build_task(x, action)
        self.launch_task(action)
        
    def filter_items(self, filter_txt=None):
        if filter_txt == None:
            self.filter_txt_limit_changed = True
            self.filter_txt = self.filter_le.text()
        else:
            self.filter_txt_limit_changed = False    
            self.filter_txt = filter_txt
            
        description = 'Filtering features'
        action = 'filterFeatures'
        self.build_task(description, action)
        self.launch_task(action)
    
    def build_task(self, description, action, silent_flag=False):

        # for key in self.tasks[action].keys():
        #     if key == self.layer.id():
        #         if isinstance(self.tasks[action][key], QgsTask):
        #             self.tasks[action][key].cancel()
  
        self.tasks[action][self.layer.id()] = PopulateListEngineTask(description, self, action, silent_flag)
        self.tasks[action][self.layer.id()].setDependentLayers([self.layer])


        if silent_flag is False:
            try:
                self.tasks[action][self.layer.id()].begun.connect(lambda:  iface.messageBar().pushMessage(self.layer.name() + " : " + description))
            except:
                pass


    def launch_task(self, action):

        self.tasks[action][self.layer.id()].taskCompleted.connect(self.connect_filter_lineEdit)
        QgsApplication.taskManager().addTask(self.tasks[action][self.layer.id()])


    def updatedCheckedItemListEvent(self, data, flag):
        self.list_widgets[self.layer.id()].setSelectedFeaturesList(data)
        self.updatingCheckedItemList.emit(data, flag)

    def filteredCheckedItemListEvent(self, data, flag):
        self.list_widgets[self.layer.id()].setVisibleFeaturesList(data)
        self.filteringCheckedItemList.emit()



class ListWidgetWrapper(QListWidget):
  
    def __init__(self, identifier_field_name, primary_key_is_numeric, parent=None):

        super(ListWidgetWrapper, self).__init__(parent)

        self.setMinimumHeight(100)
        self.identifier_field_name = identifier_field_name
        self.identifier_field_type_numeric = primary_key_is_numeric
        self.filter_expression = ''
        self.filter_text = ''
        self.display_expression = ''
        self.field_flag = False
        self.subset_string = ''
        self.features_list = []
        self.filter_expression_features_id_list = []
        self.visible_features_list = []
        self.selected_features_list = []
        self.limit = 1000
        self.total_features_list_count = 0

    def setFilterExpression(self, filter_expression):
        self.filter_expression = filter_expression

    def setIdentifierFieldName(self, identifier_field_name):
        self.identifier_field_name = identifier_field_name

    def setFilterText(self, filter_text):
        self.filter_text = filter_text

    def setDisplayExpression(self, display_expression):
        self.display_expression = display_expression

    def setExpressionFieldFlag(self, field_flag):
        self.field_flag = field_flag    
    
    def setSubsetString(self, subset_string):
        self.subset_string = subset_string

    def setTotalFeaturesListCount(self, total_features_list_count):
        self.total_features_list_count = total_features_list_count

    def setFeaturesList(self, features_list):
        self.features_list = features_list

    def setFilterExpressionFeaturesIdList(self, filter_expression_features_id_list):
        self.filter_expression_features_id_list = filter_expression_features_id_list

    def setVisibleFeaturesList(self, visible_features_list):
        self.visible_features_list = visible_features_list

    def setSelectedFeaturesList(self, selected_features_list):
        self.selected_features_list = selected_features_list
    
    def setLimit(self, limit):
        self.limit = limit

    def getFilterExpression(self):
        return self.filter_expression

    def getIdentifierFieldName(self):
        return self.identifier_field_name
    
    def getFilterText(self):
        return self.filter_text

    def getDisplayExpression(self):
        return self.display_expression
    
    def getExpressionFieldFlag(self):
        return self.field_flag
    
    def getSubsetString(self):
        return self.subset_string
    
    def getTotalFeaturesListCount(self):
        return self.total_features_list_count
      
    def getFilterExpressionFeaturesIdList(self):
        return self.filter_expression_features_id_list

    def getFeaturesList(self):
        return self.features_list
    
    def getVisibleFeaturesList(self):
        return self.visible_features_list
    
    def getSelectedFeaturesList(self):
        return self.selected_features_list

    def getLimit(self):
        return self.limit
    
    def sortFeaturesListByDisplayExpression(self, nonSubset_features_list=[]):
        self.features_list.sort(key=lambda k: (k[1] not in nonSubset_features_list, k[0]))


class QgsCheckableComboBoxLayer(QComboBox):
    

    checkedItemsChanged = pyqtSignal(list)

    def __init__(self, parent=None):
        super(QgsCheckableComboBoxLayer, self).__init__(parent)

        self.parent = parent
        self.setBaseSize(30, 0)
        self.setMinimumHeight(30)
        self.setMinimumWidth(30)
        self.setMaximumHeight(30)
        self.setMaximumWidth(16777215)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)

        font = QFont("Segoe UI Semibold", 8)
        font.setBold(True)
        self.setFont(font)

        #self.view().pressed.connect(self.handleItemPressed)
        self.setModel(QtGui.QStandardItemModel(self))
        self.setItemDelegate(ItemDelegate(self))
        self.createMenuContext()

        self.view().setModel(self.model())
        
        self.installEventFilter(self)
        self.view().viewport().installEventFilter(self)


    def createMenuContext(self):
        self.context_menu = QMenu(self)
        
        self.action_check_all = QAction('Select All', self)
        self.action_check_all.triggered.connect(self.select_all)
        self.action_uncheck_all = QAction('De-select All', self)
        self.action_uncheck_all.triggered.connect(self.deselect_all)
        self.action_check_all_geometry_line = QAction('Select all layers by geometry type (Lines)', self)
        self.action_check_all_geometry_line.triggered.connect(partial(self.select_by_geometry, 'GeometryType.Line', Qt.Checked))
        self.action_uncheck_all_geometry_line = QAction('De-Select all layers by geometry type (Lines)', self)
        self.action_uncheck_all_geometry_line.triggered.connect(partial(self.select_by_geometry, 'GeometryType.Line', Qt.Unchecked))
        self.action_check_all_geometry_point = QAction('Select all layers by geometry type (Points)', self)
        self.action_check_all_geometry_point.triggered.connect(partial(self.select_by_geometry, 'GeometryType.Point', Qt.Checked))
        self.action_uncheck_all_geometry_point = QAction('De-Select all layers by geometry type (Lines)', self)
        self.action_uncheck_all_geometry_point.triggered.connect(partial(self.select_by_geometry, 'GeometryType.Point', Qt.Unchecked))
        self.action_check_all_geometry_polygon = QAction('Select all layers by geometry type (Polygons)', self)
        self.action_check_all_geometry_polygon.triggered.connect(partial(self.select_by_geometry, 'GeometryType.Polygon', Qt.Checked))
        self.action_uncheck_all_geometry_polygon = QAction('De-Select all layers by geometry type (Polygon)', self)
        self.action_uncheck_all_geometry_polygon.triggered.connect(partial(self.select_by_geometry, 'GeometryType.Polygon', Qt.Unchecked))

        self.context_menu.addAction(self.action_check_all)
        self.context_menu.addAction(self.action_uncheck_all)
        self.context_menu.addSeparator()    
        self.context_menu.addAction(self.action_check_all_geometry_line)
        self.context_menu.addAction(self.action_uncheck_all_geometry_line)
        self.context_menu.addSeparator()    
        self.context_menu.addAction(self.action_check_all_geometry_point)
        self.context_menu.addAction(self.action_uncheck_all_geometry_point)
        self.context_menu.addSeparator()        
        self.context_menu.addAction(self.action_check_all_geometry_polygon)
        self.context_menu.addAction(self.action_uncheck_all_geometry_polygon)

            
    def addItem(self, icon, text, data=None):

        item = QStandardItem()
        item.setCheckable(True)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
        item.setData(Qt.Unchecked, Qt.CheckStateRole)
        item.setText(text)
        item.setData(text, role=Qt.DisplayRole)
        item.setData(icon, role=Qt.DecorationRole)


        if data != None:
            item.setData(data, role=Qt.UserRole)

        
        
    
        self.model().appendRow(item)



    def setItemCheckState(self, i, state=None):
        item = self.model().item(i)
        if state != None:
            item.setCheckState(state)
        else:
            state = item.data(Qt.CheckStateRole)
            if state == Qt.Checked:
                item.setCheckState(Qt.Unchecked)
            elif state == Qt.Unchecked:
                item.setCheckState(Qt.Checked)

    def setItemsCheckState(self, input_list, state):
        assert isinstance(input_list, list)
        for i in input_list:
            item = self.model().item(i)
            item.setCheckState(state)
        self.checkedItemsChangedEvent()

            
    def setCheckedItems(self, input_list):
        assert isinstance(input_list, list)
        for text in input_list:
            items = self.model().findItems(text)
            for item in items:
                item.setCheckState(Qt.Checked)
    

    def select_all(self):
        for i in range(self.count()):
            item = self.model().item(i)
            item.setCheckState(Qt.Checked)
        self.checkedItemsChangedEvent()

    def deselect_all(self):
        for i in range(self.count()):
            item = self.model().item(i)
            item.setCheckState(Qt.Unchecked)       
        self.checkedItemsChangedEvent()

    def select_by_geometry(self, geometry_type, state):
        items_to_be_checked = []
        for i in range(self.count()):
            item = self.model().item(i)
            data = item.data(Qt.UserRole)
            if data:
                if data["layer_geometry_type"] == geometry_type:
                    items_to_be_checked.append(i)
        self.setItemsCheckState(items_to_be_checked, state)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonRelease and obj == self.view().viewport() and event.button() == Qt.LeftButton:
            index = self.view().currentIndex()
            item = self.model().itemFromIndex(index)
            state = index.data(Qt.CheckStateRole)
            if state == Qt.Checked:
                item.setCheckState(Qt.Unchecked)
            elif state == Qt.Unchecked:
                item.setCheckState(Qt.Checked)
            return True
        elif event.type() == QEvent.MouseButtonRelease and obj in [self.view().viewport(), self] and event.button() == Qt.RightButton:
            action = self.context_menu.exec_(QCursor.pos())
            if action:
                return True
            else:
                return False
        return False



    def itemCheckState(self, i):
        item = self.model().item(i)
        if item:
            return item.checkState()
    

    def checkedItems(self):
        checked_items = []
        for i in range(self.count()):
            item = self.model().item(i)
            if item.checkState() == Qt.Checked:
                checked_items.append(item.text())
        checked_items.sort()
        return checked_items



        
    def checkedItemsChangedEvent(self):
        event = self.checkedItems()
        self.checkedItemsChanged.emit(event)

    def paintEvent(self, event):
        painter = QStylePainter(self)
        painter.setPen(self.palette().color(QPalette.Text))
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        opt.currentText = ",".join(self.checkedItems())
        painter.drawComplexControl(QStyle.CC_ComboBox, opt)
        painter.drawControl(QStyle.CE_ComboBoxLabel, opt)


class ItemDelegate(QtWidgets.QStyledItemDelegate):

    def __init__(self, parent=None, *args):
        QtWidgets.QStyledItemDelegate.__init__(self, parent, *args)
        self.parent = parent


    # overrides
    def sizeHint(self, option, index):
        ish = option.decorationSize.height()
        isw = option.decorationSize.width()
        return QtCore.QSize(isw, ish)


    def getCheckboxRect(self, option):
        return QtCore.QRect(4, 4, 18, 18).translated(option.rect.topLeft())
    
    def getItemRect(self, item):
        size_hint = item.sizeHint()
        return QtCore.QRect(0, 0, size_hint.width(), size_hint.height())

    def paint(self, painter, option, index):
        painter.save()


        # Draw
        ish = option.decorationSize.height()
        isw = option.decorationSize.width()
        x, y, dx, dy = option.rect.x(), option.rect.y(), option.rect.width(), option.rect.height()


        text = index.data(QtCore.Qt.DisplayRole)
        if text:
           painter.drawText(x + isw*2 + 4, y + 4 + ish/2 , text)

        # Decoration
        pic = index.data(QtCore.Qt.DecorationRole)
        if pic:
            painter.drawPixmap(x + isw, y, pic.pixmap(isw, ish))

        # Indicate Selected
        painter.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        if option.state & QtWidgets.QStyle.State_Selected:
            painter.setBrush(QtGui.QBrush(QtGui.QColor(0,70,240,128)))
        else:
            painter.setBrush(QtGui.QBrush(QtCore.Qt.NoBrush))
        painter.drawRect(QtCore.QRect(x, y, dx, dy))

        # Checkstate
        value = index.data(QtCore.Qt.CheckStateRole)
        if value is not None:
            opt = QtWidgets.QStyleOptionViewItem()
            opt.rect = self.getCheckboxRect(option)
            opt.state = opt.state & ~QtWidgets.QStyle.State_HasFocus
            if value == QtCore.Qt.Unchecked:
                opt.state |= QtWidgets.QStyle.State_Off
            elif value == QtCore.Qt.PartiallyChecked:
                opt.state |= QtWidgets.QStyle.State_NoChange
            elif value == QtCore.Qt.Checked:
                opt.state = QtWidgets.QStyle.State_On
            style = QtWidgets.QApplication.style()
            style.drawPrimitive(
                QtWidgets.QStyle.PE_IndicatorViewItemCheck, opt, painter, None
            )


        painter.restore()
