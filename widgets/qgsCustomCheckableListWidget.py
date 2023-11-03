from qgis.PyQt import QtGui, QtWidgets, uic
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *
from qgis.utils import iface
from qgis.PyQt.QtWidgets import QApplication, QVBoxLayout


class PopulateListEngineTask(QgsTask):
    """Main QgsTask class which filter and unfilter data"""

    def __init__(self, description, parent, action, silent_flag):

        QgsTask.__init__(self, description, QgsTask.CanCancel)

        self.exception = None
        
        self.action = action

        self.parent = parent

        self.silent_flag = silent_flag
        self.layer = self.parent.layer
        self.identifier_field_name = self.parent.list_widgets[self.layer.id()].getIdentifierFieldName()
        self.expression = self.parent.list_widgets[self.layer.id()].getExpression()
        self.is_field_flag = self.parent.list_widgets[self.layer.id()].getExpressionFieldFlag()


    def run(self):
        """Main function that run the right method from init parameters"""
        try:
            if self.action == 'buildFeaturesList':
                self.buildFeaturesList()
            elif self.action == 'updateFeaturesList':
                self.updateFeaturesList()
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

        
    
    def buildFeaturesList(self):
        
        item_list = []


        if self.parent.list_widgets[self.layer.id()].getFilterExpression() != '':
            filter_expression = self.parent.list_widgets[self.layer.id()].getFilterExpression()
            if QgsExpression(filter_expression).isValid():
                self.layer.selectByExpression(filter_expression)
                total_count = self.layer.selectedFeatureCount()
                self.layer.removeSelection()

                if self.is_field_flag is True:
                    for index, feature in enumerate(self.layer.getFeatures(QgsFeatureRequest(QgsExpression(filter_expression)))):
                        arr = [feature[self.expression], feature[self.identifier_field_name]]
                        item_list.append(arr)
                        self.setProgress((index/total_count)*100)
                else:
                    expression = QgsExpression(self.expression)

                    if expression.isValid():
                        
                        context = QgsExpressionContext()
                        scope = QgsExpressionContextScope()
                        context.appendScope(scope)


                        for index, feature in enumerate(self.layer.getFeatures(QgsFeatureRequest(QgsExpression(filter_expression)))):
                            scope.setFeature(feature)
                            result = expression.evaluate(context)
                            if result:
                                arr = [result, feature[self.identifier_field_name]]
                                item_list.append(arr)
                                self.setProgress((index/total_count)*100)

        else:
            total_count = self.layer.featureCount()

            if self.is_field_flag is True:
                for index, feature in enumerate(self.layer.getFeatures()):
                    arr = [feature[self.expression], feature[self.identifier_field_name]]
                    item_list.append(arr)
                    self.setProgress((index/total_count)*100)
            else:
                expression = QgsExpression(self.expression)

                if expression.isValid():
                    
                    context = QgsExpressionContext()
                    scope = QgsExpressionContextScope()
                    context.appendScope(scope)


                    for index, feature in enumerate(self.layer.getFeatures()):
                        scope.setFeature(feature)
                        result = expression.evaluate(context)
                        if result:
                            arr = [result, feature[self.identifier_field_name]]
                            item_list.append(arr)
                            self.setProgress((index/total_count)*100)

        self.parent.list_widgets[self.layer.id()].setList(item_list)
        self.parent.list_widgets[self.layer.id()].sortList()


    def selectAllFeatures(self):
        total_count = self.parent.list_widgets[self.layer.id()].count()
        for index, it in enumerate(range(self.parent.list_widgets[self.layer.id()].count())):
            item = self.parent.list_widgets[self.layer.id()].item(it)
            if not item.isHidden():
                item.setCheckState(Qt.Checked)
            self.setProgress((index/total_count)*100)
        self.updateFeatures()


    def deselectAllFeatures(self):
        total_count = self.parent.list_widgets[self.layer.id()].count()
        for index, it in enumerate(range(self.parent.list_widgets[self.layer.id()].count())):
            item = self.parent.list_widgets[self.layer.id()].item(it)
            if not item.isHidden():
                item.setCheckState(Qt.Unchecked)
            self.setProgress((index/total_count)*100)
        self.updateFeatures()


    def loadFeaturesList(self, custom_list=None, new_list=True, has_limit=True):
        current_selected_features_list = [feature[1] for feature in self.parent.list_widgets[self.layer.id()].getSelectedFeaturesList()]
        
        if custom_list == None:
            if self.parent.list_widgets[self.layer.id()].getFilterExpression() == '':
                list_to_load = self.parent.list_widgets[self.layer.id()].getList()
            elif self.parent.list_widgets[self.layer.id()].getFilterExpression() != '':
                list_to_load = self.parent.list_widgets[self.layer.id()].getList()
        else:
            list_to_load = custom_list
        
        if new_list is True:
            self.parent.list_widgets[self.layer.id()].clear()

        if has_limit is True:
            limit = self.parent.list_widgets[self.layer.id()].getLimit()

            total_count = len(list_to_load[:limit])
            for index, it in enumerate(list_to_load[:limit]):
                lwi = QListWidgetItem(str(it[0]))
                lwi.setData(0,it[0])
                lwi.setData(3,it[1])
                lwi.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                if it[1] in current_selected_features_list:
                    lwi.setCheckState(Qt.Checked)
                else:
                    lwi.setCheckState(Qt.Unchecked)
                self.parent.list_widgets[self.layer.id()].addItem(lwi)
                self.setProgress((index/total_count)*100)
        
        else:
            total_count = len(list_to_load)
            for index, it in enumerate(list_to_load):
                lwi = QListWidgetItem(str(it[0]))
                lwi.setData(0,it[0])
                lwi.setData(3,it[1])
                lwi.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                if it[1] in current_selected_features_list:
                    lwi.setCheckState(Qt.Checked)
                else:
                    lwi.setCheckState(Qt.Unchecked)
                self.parent.list_widgets[self.layer.id()].addItem(lwi)
                self.setProgress((index/total_count)*100)
        self.updateFeatures()

            
    def filterFeatures(self):
        total_count = self.parent.list_widgets[self.layer.id()].count()
        filter_txt_splitted = self.parent.filter_txt.lower().strip().replace('é','e').replace('è','e').replace('â','a').replace('ô','o').split(" ")

        if self.parent.list_widgets[self.layer.id()].getListCount() != total_count:
            features_to_load = []
            for index, feature in enumerate(self.parent.list_widgets[self.layer.id()].getList()):
                string_value = str(feature[0]).strip().lower().replace('é','e').replace('è','e').replace('â','a').replace('ô','o')
                if all(x in string_value for x in filter_txt_splitted):
                    features_to_load.append(feature)
                self.setProgress((index/total_count)*100)
            self.loadFeaturesList(features_to_load, True, False)

        else:
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
                visible_features_list.append([item.data(0), item.data(3)])

        self.parent.filteredCheckedItemListEvent(visible_features_list, True)


    
    def updateFeatures(self):
        self.parent.items_le.clear()
        selection_data = []
        total_count = self.parent.list_widgets[self.layer.id()].count()
        for index, it in enumerate(range(self.parent.list_widgets[self.layer.id()].count())):
            item = self.parent.list_widgets[self.layer.id()].item(it)
            if item.checkState() == Qt.Checked:
                selection_data.append([item.data(0), item.data(3)])
            self.setProgress((index/total_count)*100)
        selection_data.sort(key=lambda k: k[0])
        self.parent.items_le.setText(', '.join([data[0] for data in selection_data]))
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


class QgsCustomCheckableListWidget(QWidget):
    '''
    Copy and paste this class into your PyQGIS project/ plugin
    '''
    updatingCheckedItemList = pyqtSignal(list, bool)
    filteringCheckedItemList = pyqtSignal()
    
    def __init__(self, parent=None):
        self.parent = parent
        QDialog.__init__(self)
        self.layout = QVBoxLayout(self)
        self.filter_le = QLineEdit(self)
        self.filter_le.setPlaceholderText('Type to filter...')
        self.items_le = QLineEdit(self)
        self.items_le.setReadOnly(True)

        self.layout.addWidget(self.filter_le)
        self.layout.addWidget(self.items_le)

        self.context_menu = QMenu(self)
        self.action_check_all = QAction('Select All', self)
        self.action_check_all.triggered.connect(self.select_all)
        self.action_uncheck_all = QAction('De-select All', self)
        self.action_uncheck_all.triggered.connect(self.deselect_all)
        self.context_menu.addAction(self.action_check_all)
        self.context_menu.addAction(self.action_uncheck_all)

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
                selection.append([item.data(0), item.data(3)])
        selection.sort(key=lambda k: k[0])
        return selection

    def displayExpression(self):
        if self.layer != None:
            return self.list_widgets[self.layer.id()].getExpression()
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
        
    def setLayer(self, layer, layer_props=None):

        if layer != None:
            if self.layer != None:
                self.list_widgets[self.layer.id()].setFilterText(self.filter_le.text())
                self.filter_le.clear()
                self.items_le.clear()

            self.layer = layer

            self.manage_list_widgets()
            

            self.filter_le.setText(self.list_widgets[self.layer.id()].getFilterText())

            if self.list_widgets[self.layer.id()].getIdentifierFieldName() == '':
                self.list_widgets[self.layer.id()].setIdentifierFieldName(layer_props["infos"]["primary_key_name"])

            if self.list_widgets[self.layer.id()].getExpression() != layer_props["exploring"]["multiple_selection_expression"]:
                self.setDisplayExpression(layer_props["exploring"]["multiple_selection_expression"])
            elif layer_props["infos"]["is_already_subset"] != self.list_widgets[self.layer.id()].getSubsetState():
                if self.layer.featureCount() != self.list_widgets[self.layer.id()].getListCount():
                    self.setDisplayExpression(layer_props["exploring"]["multiple_selection_expression"])
            else:
                description = 'Selecting feature'
                action = 'updateFeatures'
                self.build_task(description, action, True)
                self.launch_task(action)
            
            self.list_widgets[self.layer.id()].setSubsetState(layer_props["infos"]["is_already_subset"])


    def setFilterExpression(self, filter_expression):
        if self.layer != None:
            if filter_expression != self.list_widgets[self.layer.id()].getFilterExpression():
                if QgsExpression(filter_expression).isField() is False:
                    self.list_widgets[self.layer.id()].setFilterExpression(filter_expression)
                    expression = self.list_widgets[self.layer.id()].getExpression()
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

            self.list_widgets[self.layer.id()].setExpression(working_expression)

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
            if event.button() == Qt.LeftButton:
                clicked_item = self.list_widgets[self.layer.id()].itemAt(event.pos())
                if clicked_item.checkState() == Qt.Checked:
                    clicked_item.setCheckState(Qt.Unchecked)
                else:
                    clicked_item.setCheckState(Qt.Checked)

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
            if self.list_widgets[self.layer.id()].getListCount() == self.list_widgets[self.layer.id()].count():
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


    def manage_list_widgets(self):
        for key in self.list_widgets.keys():
            self.list_widgets[key].setVisible(False)

        if self.layer.id() in self.list_widgets:
            self.list_widgets[self.layer.id()].setVisible(True)
        else:
            self.add_list_widget()


    def add_list_widget(self):
        self.list_widgets[self.layer.id()] = ListWidgetWrapper(self)
        self.list_widgets[self.layer.id()].viewport().installEventFilter(self)
        self.layout.addWidget(self.list_widgets[self.layer.id()])


    def select_all(self):
        description = 'Selecting all features'
        action = 'selectAllFeatures'
        self.build_task(description, action)
        self.launch_task(action)

    def deselect_all(self):
        description = 'Deselecting all features'
        action = 'deselectAllFeatures'
        self.build_task(description, action)
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
        self.tasks[action][self.layer.id()] = PopulateListEngineTask(description, self, action, silent_flag)
        self.tasks[action][self.layer.id()].setDependentLayers([self.layer])

        if silent_flag is False:
            self.tasks[action][self.layer.id()].begun.connect(lambda:  iface.messageBar().pushMessage(self.layer.name() + " : " + description))

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
  
    def __init__(self, parent=None):

        super(ListWidgetWrapper, self).__init__(parent)

        self.setMinimumHeight(100)
        self.subset_state = False
        self.filter_expression = ''
        self.identifier_field_name = ''
        self.filter_text = ''
        self.expression = ''
        self.field_flag = None
        self.list = []
        self.visible_features_list = []
        self.selected_features_list = []
        self.limit = 1000

    def setSubsetState(self, subset_state):
        self.subset_state = subset_state

    def setFilterExpression(self, filter_expression):
        self.filter_expression = filter_expression

    def setIdentifierFieldName(self, identifier_field_name):
        self.identifier_field_name = identifier_field_name

    def setFilterText(self, filter_text):
        self.filter_text = filter_text

    def setExpression(self, expression):
        self.expression = expression

    def setExpressionFieldFlag(self, field_flag):
        self.field_flag = field_flag    
    
    def setList(self, list):
        self.list = list

    def setVisibleFeaturesList(self, visible_features_list):
        self.visible_features_list = visible_features_list

    def setSelectedFeaturesList(self, selected_features_list):
        self.selected_features_list = selected_features_list
    
    def setLimit(self, limit):
        self.limit = limit

    def getSubsetState(self):
        return self.subset_state

    def getFilterExpression(self):
        return self.filter_expression

    def getIdentifierFieldName(self):
        return self.identifier_field_name
    
    def getFilterText(self):
        return self.filter_text

    def getExpression(self):
        return self.expression
    
    def getExpressionFieldFlag(self):
        return self.field_flag
    
    def getList(self):
        return self.list
    
    def getVisibleFeaturesList(self):
        return self.visible_features_list
    
    def getSelectedFeaturesList(self):
        return self.selected_features_list

    def getLimit(self):
        return self.limit

    def getListCount(self):
        return len(self.list) if isinstance(self.list, list) else 0
    
    def sortList(self):
        self.list.sort(key=lambda k: k[0])
