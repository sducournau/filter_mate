class SignalStateChangeError(Exception):
    """Exception raised for errors when changing a widget's signal state.

    Attributes:
        input_state -- input state which caused the error
        widget_path -- name of the concerned widget
        message -- explanation of the error
    """

    def __init__(self, input_state, widget_path, message=None):
        self.input_state = input_state
        self.widget_path = widget_path
        if message != None:
            self.input_message = message
        else:
            if self.input_state == None:
                self.input_message = "Signal doesn't exists"
            else:
                self.input_message = "Cannot change signal state"
        

        self.message = "{widget_name} : {message}".format(widget_name='.'.join(self.widget_path), message=self.input_message)
        
        super().__init__(self.message)