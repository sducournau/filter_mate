# -*- coding: utf-8 -*-
"""
QProxyStyle fix for QToolBox tab icon vertical alignment.

Qt5 bug: In QCommonStyle::drawControl(CE_ToolBoxTabLabel), the icon rect
height is set to the icon's pixel height instead of the content rect height.
This causes the icon to be top-aligned while text is vertically centered.

This proxy style overrides CE_ToolBoxTabLabel to use the full content height
for the icon rect, so Qt.AlignCenter properly centers the icon vertically.
"""

from qgis.PyQt import QtCore, QtGui
from qgis.PyQt.QtWidgets import QProxyStyle, QStyle, QStyleOptionToolBox
from qgis.PyQt.QtCore import Qt


class ToolBoxIconAlignStyle(QProxyStyle):
    """QProxyStyle that fixes vertical alignment of icons in QToolBox tabs."""

    def drawControl(self, element, option, painter, widget=None):
        if element != QStyle.CE_ToolBoxTabLabel:
            super().drawControl(element, option, painter, widget)
            return

        if not isinstance(option, QStyleOptionToolBox) or option.icon.isNull():
            super().drawControl(element, option, painter, widget)
            return

        enabled = bool(option.state & QStyle.State_Enabled)
        icon_size = self.proxy().pixelMetric(QStyle.PM_SmallIconSize, option, widget)
        pm = option.icon.pixmap(
            icon_size,
            QtGui.QIcon.Normal if enabled else QtGui.QIcon.Disabled
        )
        cr = self.subElementRect(QStyle.SE_ToolBoxTabContents, option, widget)

        iw = int(pm.width() / pm.devicePixelRatio()) + 4
        # FIX: Use cr.height() for icon rect (Qt uses icon pixel height, causing top-alignment)
        ir = QtCore.QRect(cr.left() + 4, cr.top(), iw + 2, cr.height())
        tr = QtCore.QRect(ir.right(), cr.top(), cr.width() - ir.right() - 4, cr.height())

        self.proxy().drawItemPixmap(painter, ir, Qt.AlignCenter, pm)

        txt = option.fontMetrics.elidedText(option.text, Qt.ElideRight, tr.width())
        self.proxy().drawItemText(
            painter, tr, Qt.AlignLeft | Qt.AlignVCenter, option.palette,
            enabled, txt, QtGui.QPalette.ButtonText
        )
