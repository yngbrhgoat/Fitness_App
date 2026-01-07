from __future__ import annotations

import calendar
import sqlite3
from datetime import date, datetime
from functools import partial
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

from kivy.config import Config

# Avoid probing input devices via xinput under Xwayland.
Config.remove_option("input", "%(name)s")

from kivy.app import App
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.screenmanager import Screen
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.metrics import dp

import exercise_database
import localization

KV = """
#:import dp kivy.metrics.dp

<Button>:
    background_normal: ""
    background_down: ""
    background_color: 0.18, 0.4, 0.85, 1
    color: 1, 1, 1, 1

<AppSpinnerOption@SpinnerOption>:
    background_normal: ""
    background_down: ""
    background_color: 0.92, 0.96, 1, 1
    color: 0, 0, 0, 1
    canvas.after:
        Color:
            rgba: 0.75, 0.8, 0.9, 1
        Line:
            points: [self.x + dp(6), self.y, self.right - dp(6), self.y]
            width: 1

<Spinner>:
    option_cls: "AppSpinnerOption"
    on_text: app.root.confirm_value_input(self)

<TextInput>:
    on_focus: app.root.confirm_value_input(self) if not self.focus else None

<FilterLabel@Label>:
    color: 0.2, 0.2, 0.25, 1
    font_size: "13sp"
    size_hint_y: None
    height: dp(18)
    text_size: self.size
    valign: "middle"

<WrapLabel@Label>:
    text_size: self.width, None
    size_hint_y: None
    height: self.texture_size[1]
    halign: "left"
    valign: "middle"

<DetailCard@BoxLayout>:
    orientation: "vertical"
    size_hint_y: None
    height: self.minimum_height
    padding: dp(10)
    spacing: dp(6)
    canvas.before:
        Color:
            rgba: 0.97, 0.98, 1, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [8,]
    canvas.after:
        Color:
            rgba: 0.84, 0.88, 0.94, 1
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, 8)
            width: 1

<DetailRow>:
    orientation: "horizontal"
    size_hint_y: None
    height: self.minimum_height
    padding: dp(8), dp(6)
    spacing: dp(8)
    canvas.before:
        Color:
            rgba: 1, 1, 1, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [6,]
    canvas.after:
        Color:
            rgba: 0.86, 0.89, 0.95, 1
        Line:
            rounded_rectangle: (self.x, self.y, self.width, self.height, 6)
            width: 1
    Label:
        text: root.label_text
        bold: True
        color: 0.15, 0.18, 0.28, 1
        size_hint_x: 0.4
        size_hint_y: None
        height: self.texture_size[1]
        halign: "left"
        valign: "middle"
        text_size: self.size
    WrapLabel:
        text: root.value_text
        color: 0.16, 0.2, 0.3, 1
        size_hint_x: 0.6

<StatusBanner@BoxLayout>:
    text: ""
    status_color: 0.14, 0.4, 0.2, 1
    is_error: False
    size_hint_y: None
    height: self.minimum_height if self.text else 0
    opacity: 1 if self.text else 0
    padding: dp(10), dp(8)
    spacing: dp(8)
    canvas.before:
        Color:
            rgba: (self.status_color[0], self.status_color[1], self.status_color[2], 0.14) if self.text else (0, 0, 0, 0)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [8,]
    Label:
        text: "!" if root.is_error else "i"
        color: root.status_color
        bold: True
        size_hint_x: None
        width: dp(18)
        valign: "middle"
        text_size: self.size
    WrapLabel:
        text: root.text
        color: root.status_color
        bold: True if root.is_error else False
        font_size: "16sp" if root.is_error else "15sp"

<EmptyStateCard@BoxLayout>:
    text: ""
    size_hint_y: None
    height: self.minimum_height if self.text else 0
    opacity: 1 if self.text else 0
    padding: dp(14)
    canvas.before:
        Color:
            rgba: 0.98, 0.96, 0.9, 1 if self.text else 0
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [10,]
    WrapLabel:
        text: root.text
        color: 0.35, 0.28, 0.2, 1
        font_size: "15sp"
        bold: True
        halign: "center"

<InstructionBadge@Label>:
    text_size: self.width - dp(20), None
    size_hint_y: None
    height: self.texture_size[1] + dp(14)
    padding: dp(10), dp(6)
    font_size: "20sp"
    bold: True
    color: 1, 1, 1, 1
    canvas.before:
        Color:
            rgba: 0.2, 0.45, 0.8, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [10,]

<ProgressRing>:
    canvas:
        Color:
            rgba: root.background_color
        Line:
            width: root.thickness
            circle: (self.center_x, self.center_y, min(self.width, self.height) / 2 - root.thickness / 2)
        Color:
            rgba: root.color
        Line:
            width: root.thickness
            cap: "round"
            circle: (self.center_x, self.center_y, min(self.width, self.height) / 2 - root.thickness / 2, 0, 360 * root.progress)

<GridInfoLabel@Label>:
    text_size: self.size
    halign: "left"
    valign: "middle"
    shorten: True
    shorten_from: "right"

<NavButton@Button>:
    background_normal: ""
    background_down: ""
    background_color: 0.22, 0.32, 0.45, 1
    color: 1, 1, 1, 1
    font_size: "14sp"

<ExerciseCard>:
    orientation: "vertical"
    padding: dp(12)
    spacing: dp(6)
    size_hint_y: None
    height: self.minimum_height
    on_release: app.root.open_browse_details(root.name)
    canvas.before:
        Color:
            rgba: 0.96, 0.97, 1, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [8,]
    BoxLayout:
        orientation: "horizontal"
        spacing: dp(10)
        size_hint_y: None
        height: self.minimum_height
        Image:
            source: root.icon_source
            size_hint: None, None
            size: (dp(64), dp(64)) if root.icon_source else (0, 0)
            fit_mode: "contain"
            opacity: 1 if root.icon_source else 0
        BoxLayout:
            orientation: "vertical"
            size_hint_y: None
            height: self.minimum_height
            Label:
                text: root.display_name
                font_size: "18sp"
                bold: True
                color: 0.1, 0.12, 0.2, 1
                text_size: self.width, None
                halign: "left"
                size_hint_y: None
                height: self.texture_size[1]
            Label:
                text: root.description
                color: 0.2, 0.2, 0.24, 1
                text_size: self.width, None
                size_hint_y: None
                height: self.texture_size[1]
    GridLayout:
        cols: 3
        spacing: dp(10)
        size_hint_y: None
        height: self.minimum_height
        WrapLabel:
            text: root.goal_label or "—"
            color: 0.2, 0.2, 0.3, 1
        WrapLabel:
            text: root.muscle_group or "—"
            color: 0.2, 0.2, 0.3, 1
        WrapLabel:
            text: root.equipment or "—"
            color: 0.2, 0.2, 0.3, 1
    WrapLabel:
        text: app.tr("Suitability: {value} | Est. time: {minutes} min", app.language, value=root.suitability_value or root.suitability_display, minutes=root.estimated_minutes)
        color: 0.2, 0.2, 0.3, 1
    WrapLabel:
        text: app.tr("Recommendation score: {score}", app.language, score=root.score_display)
        color: 0.16, 0.16, 0.22, 1
    Label:
        text: app.tr("Recommendation: {value}", app.language, value=root.recommendation)
        color: 0.2, 0.2, 0.28, 1
        size_hint_y: None
        height: self.texture_size[1]
        text_size: self.width, None
    BoxLayout:
        size_hint_y: None
        height: dp(36)
        spacing: dp(8)
        Button:
            text: app.tr("Details", app.language)
            on_release: app.root.open_browse_details(root.name)

<WorkoutCard>:
    orientation: "vertical"
    padding: dp(12)
    spacing: dp(6)
    size_hint_y: None
    height: self.minimum_height
    canvas.before:
        Color:
            rgba: 0.96, 0.97, 1, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [8,]
    Label:
        text: root.date_display
        font_size: "17sp"
        bold: True
        color: 0.1, 0.12, 0.2, 1
        size_hint_y: None
        height: self.texture_size[1]
    Label:
        text: app.tr("Duration: {value}", app.language, value=root.duration_display)
        color: 0.18, 0.18, 0.22, 1
        size_hint_y: None
        height: self.texture_size[1]
    Label:
        text: app.tr("Goal: {value}", app.language, value=root.goal_display)
        color: 0.16, 0.18, 0.24, 1
        size_hint_y: None
        height: self.texture_size[1]
    Label:
        text: app.tr("Completed sets: {value}", app.language, value=root.sets_display)
        color: 0.16, 0.18, 0.24, 1
        size_hint_y: None
        height: self.texture_size[1]
    Label:
        text: root.exercises_display
        color: 0.2, 0.2, 0.28, 1
        text_size: self.width, None
        size_hint_y: None
        height: self.texture_size[1]
    Label:
        text: root.attempts_display
        color: 0.18, 0.18, 0.24, 1
        text_size: self.width, None
        size_hint_y: None
        height: self.texture_size[1]

<RecommendationCard>:
    orientation: "vertical"
    padding: dp(12)
    spacing: dp(6)
    size_hint_y: None
    height: dp(240)
    canvas.before:
        Color:
            rgba: 0.9, 0.95, 1, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [8,]
    BoxLayout:
        orientation: "horizontal"
        spacing: dp(8)
        size_hint_y: None
        height: self.minimum_height
        Image:
            source: root.icon_source
            size_hint: None, None
            size: (dp(42), dp(42)) if root.icon_source else (0, 0)
            fit_mode: "contain"
            opacity: 1 if root.icon_source else 0
        Label:
            text: root.display_name
            font_size: "17sp"
            bold: True
            color: 0.1, 0.12, 0.2, 1
            size_hint_y: None
            height: self.texture_size[1]
    WrapLabel:
        text: root.description
        color: 0.1, 0.12, 0.18, 1
        text_size: self.width, None
        size_hint_y: None
        height: self.texture_size[1]
    WrapLabel:
        text: app.tr("Muscle: {muscle} | Equipment: {equipment}", app.language, muscle=root.muscle_group, equipment=root.equipment)
        color: 0.2, 0.2, 0.3, 1
        size_hint_y: None
        height: self.texture_size[1]
    WrapLabel:
        text: app.tr("Suitability: {value} | Est. time: {minutes} min", app.language, value=root.suitability, minutes=root.estimated_minutes)
        color: 0.2, 0.2, 0.3, 1
        size_hint_y: None
        height: self.texture_size[1]
    WrapLabel:
        text: app.tr("Recommendation score: {score}", app.language, score=root.score_display)
        color: 0.16, 0.16, 0.22, 1
        size_hint_y: None
        height: self.texture_size[1]
    WrapLabel:
        text: root.recommendation
        color: 0.18, 0.18, 0.24, 1
        text_size: self.width, None
        size_hint_y: None
        height: self.texture_size[1]
    BoxLayout:
        size_hint_y: None
        height: dp(36)
        spacing: dp(8)
        Button:
            text: app.tr("Add to plan", app.language)
            on_release: app.root.add_recommendation_to_plan(root.name)
        Button:
            text: app.tr("Details", app.language)
            on_release: app.root.open_recommendation_details(root.name)

<PlanItem>:
    orientation: "vertical"
    padding: dp(8)
    spacing: dp(6)
    size_hint_y: None
    height: dp(92) if root.weight_visible else dp(60)
    canvas.before:
        Color:
            rgba: 0.9, 0.95, 1, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [6,]
    BoxLayout:
        orientation: "horizontal"
        spacing: dp(8)
        size_hint_y: None
        height: dp(42)
        Image:
            source: root.icon_source
            size_hint: None, None
            size: (dp(42), dp(42)) if root.icon_source else (0, 0)
            fit_mode: "contain"
            opacity: 1 if root.icon_source else 0
        Label:
            text: root.display
            color: 0.18, 0.18, 0.24, 1
            text_size: self.width, self.height
            halign: "left"
            valign: "middle"
        Button:
            text: app.tr("Up", app.language)
            size_hint_x: None
            width: dp(70)
            on_release: app.root.move_plan_item(root.name, -1)
        Button:
            text: app.tr("Down", app.language)
            size_hint_x: None
            width: dp(70)
            on_release: app.root.move_plan_item(root.name, 1)
        Button:
            text: app.tr("Remove", app.language)
            size_hint_x: None
            width: dp(90)
            on_release: app.root.remove_plan_item(root.name)
    BoxLayout:
        orientation: "horizontal"
        spacing: dp(6)
        size_hint_y: None
        height: dp(30) if root.weight_visible else dp(0)
        opacity: 1 if root.weight_visible else 0
        Label:
            text: app.tr("Weight", app.language)
            color: 0.16, 0.18, 0.24, 1
            size_hint_x: None
            width: dp(60)
        TextInput:
            id: plan_weight_input
            text: root.weight_value_text
            multiline: False
            input_filter: "float"
            on_text_validate: app.root.update_plan_item_weight(root.name, self.text, plan_weight_unit.text)
            on_focus: app.root.update_plan_item_weight(root.name, self.text, plan_weight_unit.text) if not self.focus else None
            disabled: not root.weight_visible
        Label:
            id: plan_weight_unit
            text: root.weight_unit_text or "kg"
            color: 0.2, 0.2, 0.25, 1
            size_hint_x: None
            width: dp(32)

<DatePickerPopup>:
    size_hint: None, None
    size: dp(360), dp(450)
    auto_dismiss: False
    BoxLayout:
        orientation: "vertical"
        padding: dp(12)
        spacing: dp(8)
        canvas.before:
            Color:
                rgba: 1, 1, 1, 1
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [10,]
        BoxLayout:
            size_hint_y: None
            height: dp(26)
            spacing: dp(8)
            Label:
                text: app.tr("Select date", app.language)
                bold: True
                color: 0.12, 0.14, 0.22, 1
                valign: "middle"
                text_size: self.size
            Label:
                text: app.tr("Selected: {value}", app.language, value=root.selected_label)
                color: 0.18, 0.18, 0.24, 1
                halign: "right"
                valign: "middle"
                text_size: self.size
        BoxLayout:
            size_hint_y: None
            height: dp(36)
            spacing: dp(8)
            Button:
                text: "<"
                size_hint_x: None
                width: dp(44)
                background_normal: ""
                background_down: ""
                background_color: 0.18, 0.4, 0.85, 1
                color: 1, 1, 1, 1
                on_release: root.shift_month(-1)
            Label:
                text: root.month_label
                bold: True
                color: 0.12, 0.14, 0.22, 1
                halign: "center"
                valign: "middle"
                text_size: self.size
            Button:
                text: ">"
                size_hint_x: None
                width: dp(44)
                background_normal: ""
                background_down: ""
                background_color: 0.18, 0.4, 0.85, 1
                color: 1, 1, 1, 1
                on_release: root.shift_month(1)
        BoxLayout:
            size_hint_y: None
            height: dp(32)
            spacing: dp(6)
            Button:
                text: app.tr("<< Year", app.language)
                size_hint_x: None
                width: dp(84)
                background_normal: ""
                background_down: ""
                background_color: 0.18, 0.4, 0.85, 1
                color: 1, 1, 1, 1
                on_release: root.shift_year(-1)
            Button:
                text: app.tr("-3 mo", app.language)
                size_hint_x: None
                width: dp(70)
                background_normal: ""
                background_down: ""
                background_color: 0.18, 0.4, 0.85, 1
                color: 1, 1, 1, 1
                on_release: root.shift_month(-3)
            Widget:
            Button:
                text: app.tr("+3 mo", app.language)
                size_hint_x: None
                width: dp(70)
                background_normal: ""
                background_down: ""
                background_color: 0.18, 0.4, 0.85, 1
                color: 1, 1, 1, 1
                on_release: root.shift_month(3)
            Button:
                text: app.tr("Year >>", app.language)
                size_hint_x: None
                width: dp(84)
                background_normal: ""
                background_down: ""
                background_color: 0.18, 0.4, 0.85, 1
                color: 1, 1, 1, 1
                on_release: root.shift_year(1)
        GridLayout:
            id: day_grid
            cols: 7
            spacing: dp(6)
            padding: dp(4)
            size_hint_y: None
            row_default_height: dp(32)
            row_force_default: True
            col_force_default: True
            col_default_width: dp(40)
            height: dp(260)
        BoxLayout:
            size_hint_y: None
            height: dp(40)
            spacing: dp(8)
            Button:
                text: app.tr("Today", app.language)
                on_release: root.select_today()
            Button:
                text: app.tr("Use date", app.language)
                on_release: root.confirm_selection()
            Button:
                text: app.tr("Cancel", app.language)
                on_release: root.dismiss()

<ConfirmActionModal>:
    size_hint: None, None
    size: dp(360), dp(220)
    auto_dismiss: False
    BoxLayout:
        orientation: "vertical"
        padding: dp(12)
        spacing: dp(6)
        canvas.before:
            Color:
                rgba: 1, 1, 1, 1
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [10,]
        Label:
            text: app.tr("Please confirm", app.language)
            font_size: "18sp"
            bold: True
            color: 0.12, 0.14, 0.22, 1
            size_hint_y: None
            height: dp(24)
        Widget:
            size_hint_y: None
            height: dp(10)
        WrapLabel:
            text: root.message
            color: 0.16, 0.18, 0.24, 1
            size_hint_y: None
            height: dp(72)
            valign: "top"
            text_size: self.width, self.height
            padding: 0, 0
        BoxLayout:
            size_hint_y: None
            height: dp(40)
            spacing: dp(8)
            Button:
                text: root.cancel_label
                background_color: 0.6, 0.64, 0.7, 1
                on_release: app.root.confirm_action_modal_cancel(); root.dismiss()
            Button:
                text: root.confirm_label
                on_release: app.root.confirm_action_modal_ok(); root.dismiss()

<DeleteUserModal>:
    size_hint: None, None
    size: dp(360), dp(240)
    auto_dismiss: False
    BoxLayout:
        orientation: "vertical"
        padding: dp(12)
        spacing: dp(8)
        canvas.before:
            Color:
                rgba: 1, 1, 1, 1
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [10,]
        Label:
            text: app.tr("Delete user", app.language)
            font_size: "18sp"
            bold: True
            color: 0.12, 0.14, 0.22, 1
            size_hint_y: None
            height: dp(24)
        WrapLabel:
            text: app.tr("Select a user to delete.", app.language)
            color: 0.16, 0.18, 0.24, 1
        Spinner:
            id: delete_user_spinner
            text: app.root.delete_user_spinner_text
            values: app.root.user_options
            on_text: app.root.on_delete_user_selected(self.text)
        BoxLayout:
            size_hint_y: None
            height: dp(40)
            spacing: dp(8)
            Button:
                text: app.tr("Cancel", app.language)
                background_color: 0.6, 0.64, 0.7, 1
                on_release: app.root.dismiss_delete_user_modal(); root.dismiss()
            Button:
                text: app.tr("Continue", app.language)
                disabled: not app.root.delete_user_ready
                on_release: app.root.confirm_delete_user_selection(); root.dismiss()

<WorkoutLogModal>:
    size_hint: 0.96, 0.9
    auto_dismiss: False
    BoxLayout:
        orientation: "vertical"
        padding: dp(12)
        spacing: dp(8)
        canvas.before:
            Color:
                rgba: 1, 1, 1, 1
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [10,]
        Label:
            text: app.tr("Log a completed workout", app.language)
            font_size: "18sp"
            bold: True
            color: 0.12, 0.14, 0.22, 1
            size_hint_y: None
            height: dp(24)
        ScrollView:
            do_scroll_x: False
            BoxLayout:
                orientation: "vertical"
                spacing: dp(8)
                size_hint_y: None
                height: self.minimum_height
                GridLayout:
                    cols: 2
                    spacing: dp(8)
                    row_default_height: dp(34)
                    size_hint_y: None
                    height: self.minimum_height
                    WrapLabel:
                        text: app.tr("Workout date (YYYY-MM-DD)", app.language)
                        color: 0.18, 0.18, 0.22, 1
                    BoxLayout:
                        spacing: dp(6)
                        TextInput:
                            id: workout_date_input
                            multiline: False
                            readonly: True
                            hint_text: app.tr("pick date", app.language)
                        Button:
                            text: app.tr("Pick", app.language)
                            size_hint_x: None
                            width: dp(70)
                            on_release: app.root.open_date_picker(workout_date_input)
                    WrapLabel:
                        text: app.tr("Duration (minutes)", app.language)
                        color: 0.18, 0.18, 0.22, 1
                    TextInput:
                        id: duration_input
                        multiline: False
                        input_filter: "int"
                        hint_text: app.tr("e.g. 45", app.language)
                    WrapLabel:
                        text: app.tr("Goal (optional)", app.language)
                        color: 0.18, 0.18, 0.22, 1
                    Spinner:
                        id: workout_goal_spinner
                        text: app.root.workout_goal_spinner_text
                        values: app.root.workout_goal_options
                        on_text: app.root.workout_goal_spinner_text = self.text
                    WrapLabel:
                        text: app.tr("Total sets completed (optional)", app.language)
                        color: 0.18, 0.18, 0.22, 1
                    TextInput:
                        id: total_sets_input
                        multiline: False
                        input_filter: "int"
                        hint_text: app.tr("e.g. 12", app.language)
                    WrapLabel:
                        text: app.tr("Exercises (comma or newline separated)", app.language)
                        color: 0.18, 0.18, 0.22, 1
                    TextInput:
                        id: exercises_input
                        multiline: True
                        size_hint_y: None
                        height: dp(80)
                        hint_text: app.tr("Push-Up, Plank, Jump Rope", app.language)
                        on_text: app.root.refresh_workout_weight_inputs(self.text)
                    WrapLabel:
                        text: app.tr("Weights (optional)", app.language)
                        color: 0.18, 0.18, 0.22, 1
                        size_hint_y: None
                        height: dp(18) if app.root.history_weight_visible else dp(0)
                        opacity: 1 if app.root.history_weight_visible else 0
                    BoxLayout:
                        id: workout_weight_container
                        orientation: "vertical"
                        spacing: dp(6)
                        size_hint_y: None
                        height: self.minimum_height if app.root.history_weight_visible else dp(0)
                        opacity: 1 if app.root.history_weight_visible else 0
                    WrapLabel:
                        text: app.tr("Filter exercises", app.language)
                        color: 0.18, 0.18, 0.22, 1
                    BoxLayout:
                        spacing: dp(6)
                        TextInput:
                            id: history_exercise_filter_input
                            multiline: False
                            hint_text: app.tr("type to search", app.language)
                            on_text: app.root.filter_history_exercise_options(self.text)
                        Button:
                            text: app.tr("Clear", app.language)
                            size_hint_x: None
                            width: dp(70)
                            on_release: app.root.clear_history_exercise_filter()
                    WrapLabel:
                        text: app.tr("Add exercise from list", app.language)
                        color: 0.18, 0.18, 0.22, 1
                    BoxLayout:
                        spacing: dp(6)
                        Spinner:
                            id: history_exercise_spinner
                            text: app.root.history_exercise_spinner_text
                            values: app.root.history_exercise_filtered_options
                            on_text: app.root.history_exercise_spinner_text = self.text
                        Button:
                            text: app.tr("Add", app.language)
                            size_hint_x: None
                            width: dp(80)
                            on_release: app.root.add_history_exercise_from_menu()
        WrapLabel:
            text: app.root.history_status_text
            color: app.root.history_status_color
            font_size: app.root.history_status_font_size
        BoxLayout:
            size_hint_y: None
            height: dp(40)
            spacing: dp(8)
            Button:
                text: app.tr("Save workout", app.language)
                on_release: app.root.handle_add_workout()
            Button:
                text: app.tr("Cancel", app.language)
                on_release: root.dismiss()

<GoalPromptModal>:
    size_hint: 0.9, 0.55
    auto_dismiss: False
    BoxLayout:
        orientation: "vertical"
        padding: dp(12)
        spacing: dp(10)
        canvas.before:
            Color:
                rgba: 1, 1, 1, 1
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [10,]
        Label:
            text: app.tr("Set your training goal", app.language)
            font_size: "18sp"
            bold: True
            color: 0.12, 0.14, 0.22, 1
            size_hint_y: None
            height: dp(24)
        WrapLabel:
            text: app.tr("Choose a goal for {user}.", app.language, user=app.root.current_user_display)
            color: 0.18, 0.18, 0.24, 1
        Spinner:
            id: goal_prompt_spinner
            text: app.root.user_profile_goal
            values: app.root.user_goal_options
            on_text: app.root.user_profile_goal = self.text
        WrapLabel:
            text: app.root.user_profile_status_text
            color: app.root.user_profile_status_color
        BoxLayout:
            size_hint_y: None
            height: dp(40)
            spacing: dp(8)
            Button:
                text: app.tr("Save goal", app.language)
                on_release: app.root.save_user_profile() and root.dismiss()
            Button:
                text: app.tr("Skip for now", app.language)
                on_release: app.root.skip_goal_prompt()

<ExerciseDetailsModal>:
    size_hint: 0.96, 0.92
    auto_dismiss: False
    BoxLayout:
        orientation: "vertical"
        padding: dp(12)
        spacing: dp(10)
        canvas.before:
            Color:
                rgba: 1, 1, 1, 1
            RoundedRectangle:
                pos: self.pos
                size: self.size
                radius: [10,]
        Label:
            text: app.tr("Exercise details", app.language)
            font_size: "18sp"
            bold: True
            color: 0.12, 0.14, 0.22, 1
            size_hint_y: None
            height: dp(24)
        WrapLabel:
            text: root.exercise_name
            font_size: "20sp"
            bold: True
            color: 0.1, 0.12, 0.2, 1
        ScrollView:
            do_scroll_x: False
            bar_width: dp(6)
            BoxLayout:
                orientation: "vertical"
                spacing: dp(10)
                size_hint_y: None
                height: self.minimum_height
                DetailCard:
                    Label:
                        text: app.tr("Description", app.language)
                        bold: True
                        color: 0.12, 0.14, 0.22, 1
                        size_hint_y: None
                        height: dp(18)
                    WrapLabel:
                        text: root.description
                        color: 0.16, 0.18, 0.24, 1
                DetailCard:
                    Label:
                        text: app.tr("Execution directions", app.language)
                        bold: True
                        color: 0.12, 0.14, 0.22, 1
                        size_hint_y: None
                        height: dp(18)
                    WrapLabel:
                        text: root.execution_instructions or app.tr("No directions provided.", app.language)
                        color: 0.16, 0.18, 0.24, 1
                DetailCard:
                    Label:
                        text: app.tr("Details", app.language)
                        bold: True
                        color: 0.12, 0.14, 0.22, 1
                        size_hint_y: None
                        height: dp(18)
                    BoxLayout:
                        orientation: "vertical"
                        spacing: dp(6)
                        size_hint_y: None
                        height: self.minimum_height
                        DetailRow:
                            label_text: app.tr("Goal", app.language)
                            value_text: root.goal_label or "—"
                        DetailRow:
                            label_text: app.tr("Muscle", app.language)
                            value_text: root.muscle_group or "—"
                        DetailRow:
                            label_text: app.tr("Equipment", app.language)
                            value_text: root.equipment or "—"
                        DetailRow:
                            label_text: app.tr("Suitability", app.language)
                            value_text: root.suitability or "—"
                        DetailRow:
                            label_text: app.tr("Est. time", app.language)
                            value_text: app.tr("{minutes} min", app.language, minutes=root.estimated_minutes) if root.estimated_minutes else "—"
                        DetailRow:
                            label_text: app.tr("Score", app.language)
                            value_text: root.score_display or "—"
                        DetailRow:
                            label_text: app.tr("Sets", app.language)
                            value_text: root.sets_display
                        DetailRow:
                            label_text: app.tr("Reps", app.language)
                            value_text: root.reps_display
                        DetailRow:
                            label_text: app.tr("Time", app.language)
                            value_text: root.time_display
                DetailCard:
                    Label:
                        text: app.tr("Recommendation", app.language)
                        bold: True
                        color: 0.12, 0.14, 0.22, 1
                        size_hint_y: None
                        height: dp(18)
                    WrapLabel:
                        text: root.recommendation or "—"
                        color: 0.16, 0.18, 0.24, 1
        BoxLayout:
            size_hint_y: None
            height: dp(40)
            spacing: dp(10)
            padding: dp(6), 0
            Widget:
            Button:
                text: app.tr("Add to plan", app.language)
                size_hint: None, None
                width: dp(140) if root.show_add_button else 0
                height: dp(32)
                opacity: 1 if root.show_add_button else 0
                disabled: not root.show_add_button
                on_release: app.root.add_recommendation_to_plan(root.exercise_key) if root.show_add_button else None; root.dismiss()
            Button:
                text: app.tr("Close", app.language)
                size_hint: None, None
                width: dp(110)
                height: dp(32)
                on_release: root.dismiss()
            Widget:

<LiveScreen>:
    ScrollView:
        do_scroll_x: False
        BoxLayout:
            orientation: "vertical"
            padding: dp(16)
            spacing: dp(12)
            size_hint_y: None
            height: self.minimum_height
            canvas.before:
                Color:
                    rgba: 1, 1, 1, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            GridLayout:
                cols: 2
                spacing: dp(8)
                size_hint_y: None
                row_default_height: dp(30)
                height: self.minimum_height
                Label:
                    text: app.root.live_progress_display
                    bold: True
                    color: 0.1, 0.12, 0.2, 1
                Label:
                    text: app.root.live_state_display
                    color: 0.16, 0.2, 0.35, 1
            BoxLayout:
                size_hint_y: None
                height: dp(38) if app.root.live_signal_text else dp(0)
                padding: dp(10), dp(6)
                canvas.before:
                    Color:
                        rgba: app.root.live_signal_color if app.root.live_signal_text else (0, 0, 0, 0)
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [8,]
                Label:
                    text: app.root.live_signal_text
                    color: 1, 1, 1, 1
                    bold: True
                    opacity: 1 if app.root.live_signal_text else 0
            BoxLayout:
                orientation: "vertical"
                padding: dp(12)
                spacing: dp(6)
                size_hint_y: None
                height: self.minimum_height
                canvas.before:
                    Color:
                        rgba: 0.92, 0.97, 1, 1
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [10,]
                Label:
                    text: app.root.live_exercise_title
                    font_size: "22sp"
                    bold: True
                    color: 0.08, 0.12, 0.22, 1
                    size_hint_y: None
                    height: self.texture_size[1]
                Image:
                    source: app.root.live_icon_source
                    size_hint_y: None
                    height: dp(140) if app.root.live_icon_source else dp(0)
                    fit_mode: "contain"
                    opacity: 1 if app.root.live_icon_source else 0
                Label:
                    text: app.root.live_icon_display
                    color: 0.18, 0.2, 0.32, 1
                    size_hint_y: None
                    height: self.texture_size[1] if not app.root.live_icon_source else dp(0)
                    opacity: 0 if app.root.live_icon_source else 1
                Label:
                    text: app.tr("Target: {muscle} | Equipment: {equipment}", app.language, muscle=app.root.live_muscle_display, equipment=app.root.live_equipment_display)
                    color: 0.18, 0.18, 0.24, 1
                    size_hint_y: None
                    height: self.texture_size[1]
                Label:
                    text: app.root.live_recommendation_display
                    color: 0.16, 0.2, 0.3, 1
                    size_hint_y: None
                    height: self.texture_size[1]
                Label:
                    text: app.tr("Planned duration: {value}", app.language, value=app.root.live_exercise_target_display)
                    color: 0.14, 0.22, 0.34, 1
                    size_hint_y: None
                    height: self.texture_size[1]
                BoxLayout:
                    size_hint_y: None
                    height: dp(54) if app.root.live_reps_visible else dp(0)
                    opacity: 1 if app.root.live_reps_visible else 0
                    padding: dp(12), dp(6)
                    canvas.before:
                        Color:
                            rgba: 0.78, 0.88, 1, 1
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [8,]
                    BoxLayout:
                        Widget:
                        BoxLayout:
                            size_hint_x: None
                            width: dp(240)
                            spacing: dp(48)
                            BoxLayout:
                                orientation: "vertical"
                                spacing: dp(2)
                                size_hint_x: None
                                width: dp(96)
                                Label:
                                    text: app.tr("Reps", app.language)
                                    color: 0.2, 0.24, 0.34, 1
                                    font_size: "12sp"
                                    size_hint_y: None
                                    height: dp(16)
                                    halign: "center"
                                    valign: "middle"
                                    text_size: self.size
                                Label:
                                    text: app.root.live_reps_display
                                    color: 0.08, 0.12, 0.22, 1
                                    font_size: "28sp"
                                    bold: True
                                    halign: "center"
                                    valign: "middle"
                                    text_size: self.size
                            BoxLayout:
                                orientation: "vertical"
                                spacing: dp(2)
                                size_hint_x: None
                                width: dp(96)
                                Label:
                                    text: app.tr("Sets", app.language)
                                    color: 0.2, 0.24, 0.34, 1
                                    font_size: "12sp"
                                    size_hint_y: None
                                    height: dp(16)
                                    halign: "center"
                                    valign: "middle"
                                    text_size: self.size
                                Label:
                                    text: app.root.live_set_counter_display
                                    color: 0.12, 0.16, 0.26, 1
                                    font_size: "22sp"
                                    bold: True
                                    halign: "center"
                                    valign: "middle"
                                    text_size: self.size
                        Widget:
                BoxLayout:
                    size_hint_y: None
                    height: dp(34) if app.root.live_weight_visible else dp(0)
                    opacity: 1 if app.root.live_weight_visible else 0
                    spacing: dp(6)
                    Label:
                        text: app.tr("Weight", app.language)
                        color: 0.16, 0.18, 0.24, 1
                        size_hint_x: None
                        width: dp(70)
                    TextInput:
                        id: live_weight_input
                        text: app.root.live_weight_value_text
                        multiline: False
                        input_filter: "float"
                        on_text_validate: app.root.set_live_weight_value(self.text)
                        on_focus: app.root.set_live_weight_value(self.text) if not self.focus else None
                        disabled: not app.root.live_weight_visible
                    Label:
                        id: live_weight_unit
                        text: app.root.live_weight_unit_text
                        color: 0.2, 0.2, 0.25, 1
                        size_hint_x: None
                        width: dp(32)
                BoxLayout:
                    size_hint_y: None
                    height: dp(36)
                    spacing: dp(8)
                    Button:
                        text: app.tr("Show details", app.language) if not app.root.live_details_expanded else app.tr("Hide details", app.language)
                        size_hint_x: None
                        width: dp(150)
                        on_release: app.root.toggle_live_details()
                    Label:
                        text: app.tr("Set: {value}", app.language, value=app.root.live_current_set_display)
                        color: 0.16, 0.18, 0.24, 1
                        text_size: self.size
                        valign: "middle"
            BoxLayout:
                orientation: "vertical"
                padding: dp(10)
                spacing: dp(6)
                size_hint_y: None
                height: self.minimum_height if app.root.live_details_expanded else dp(0)
                opacity: 1 if app.root.live_details_expanded else 0
                canvas.before:
                    Color:
                        rgba: (0.95, 0.98, 1, 1) if app.root.live_details_expanded else (0, 0, 0, 0)
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [10,]
                WrapLabel:
                    text: app.root.live_exercise_description
                    color: 0.14, 0.16, 0.24, 1
                WrapLabel:
                    text: app.tr("Execution directions", app.language)
                    color: 0.12, 0.14, 0.22, 1
                    bold: True
                WrapLabel:
                    text: app.root.live_exercise_instructions or app.tr("No directions provided.", app.language)
                    color: 0.14, 0.16, 0.24, 1
                WrapLabel:
                    text: app.root.live_recommendation_display
                    color: 0.16, 0.2, 0.3, 1
            BoxLayout:
                size_hint_y: None
                height: dp(176)
                spacing: dp(12)
                padding: dp(10)
                canvas.before:
                    Color:
                        rgba: 0.94, 0.97, 1, 1
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [8,]
                ProgressRing:
                    size_hint: None, None
                    size: dp(110), dp(110)
                    thickness: dp(4)
                    color: app.root.live_progress_color
                    progress: app.root.live_exercise_progress
                    BoxLayout:
                        size_hint: None, None
                        size: self.parent.size
                        pos: self.parent.pos
                        padding: dp(12)
                        Label:
                            text: app.root.live_progress_timer
                            font_size: "16sp"
                            bold: True
                            color: 0.1, 0.12, 0.2, 1
                            halign: "center"
                            valign: "middle"
                            text_size: self.size
                BoxLayout:
                    orientation: "vertical"
                    spacing: dp(8)
                    BoxLayout:
                        size_hint_y: None
                        height: dp(78)
                        spacing: dp(8)
                        BoxLayout:
                            orientation: "vertical"
                            padding: dp(6)
                            Label:
                                text: app.tr("Set time", app.language)
                                font_size: "13sp"
                                color: 0.16, 0.18, 0.24, 1
                                size_hint_y: None
                                height: dp(18)
                            Label:
                                text: app.root.live_set_timer
                                font_size: "22sp"
                                bold: True
                                color: 0.08, 0.12, 0.22, 1
                        BoxLayout:
                            orientation: "vertical"
                            padding: dp(6)
                            Label:
                                text: app.tr("Break timer", app.language)
                                font_size: "13sp"
                                color: 0.16, 0.18, 0.24, 1
                                size_hint_y: None
                                height: dp(18)
                            Label:
                                text: app.root.live_rest_timer
                                font_size: "22sp"
                                bold: True
                                color: 0.08, 0.12, 0.22, 1
                    BoxLayout:
                        size_hint_y: None
                        height: dp(64)
                        spacing: dp(8)
                        BoxLayout:
                            orientation: "vertical"
                            padding: dp(6)
                            Label:
                                text: app.tr("Exercise time", app.language)
                                font_size: "12sp"
                                color: 0.16, 0.18, 0.24, 1
                                size_hint_y: None
                                height: dp(16)
                            Label:
                                text: app.root.live_exercise_timer
                                font_size: "18sp"
                                bold: True
                                color: 0.08, 0.12, 0.22, 1
                        BoxLayout:
                            orientation: "vertical"
                            padding: dp(6)
                            Label:
                                text: app.tr("Per-set target", app.language)
                                font_size: "12sp"
                                color: 0.16, 0.18, 0.24, 1
                                size_hint_y: None
                                height: dp(16)
                            Label:
                                text: app.root.live_set_target_display
                                font_size: "18sp"
                                bold: True
                                color: 0.08, 0.12, 0.22, 1
            BoxLayout:
                size_hint_y: None
                height: dp(52)
                spacing: dp(10)
                padding: dp(10)
                canvas.before:
                    Color:
                        rgba: 0.96, 0.98, 1, 1
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [8,]
                Button:
                    text: app.tr("START WORKOUT", app.language)
                    size_hint: None, None
                    width: dp(230) if app.root.live_active and not app.root.live_started else dp(0)
                    height: dp(46) if app.root.live_active and not app.root.live_started else dp(0)
                    opacity: 1 if app.root.live_active and not app.root.live_started else 0
                    disabled: not app.root.live_active or app.root.live_started
                    font_size: "18sp"
                    bold: True
                    background_color: 0.12, 0.72, 0.22, 1
                    on_release: app.root.start_live_workout()
                BoxLayout:
                    size_hint_x: None
                    width: dp(190)
                    spacing: dp(6)
                    Label:
                        text: app.tr("Break (s)", app.language)
                        color: 0.16, 0.18, 0.24, 1
                        size_hint_x: None
                        width: dp(80)
                    TextInput:
                        id: live_break_input
                        text: app.root.live_rest_setting_text
                        multiline: False
                        input_filter: "int"
                        size_hint_x: None
                        width: dp(90)
                        on_text_validate: app.root.set_live_rest_seconds(self.text)
                        on_focus: app.root.set_live_rest_seconds(self.text) if not self.focus else None
                Label:
                    text: app.tr("Applies after each exercise and when tapping Next.", app.language)
                    color: 0.18, 0.2, 0.28, 1
            InstructionBadge:
                text: app.root.live_instruction
            WrapLabel:
                text: app.root.live_tempo_hint
                color: 0.12, 0.18, 0.34, 1
            WrapLabel:
                text: app.root.live_hint_text
                color: app.root.live_hint_color
                bold: True
            Label:
                text: app.tr("Upcoming: {value}", app.language, value=app.root.live_upcoming_display)
                color: 0.16, 0.16, 0.22, 1
                text_size: self.width, None
                size_hint_y: None
                height: self.texture_size[1]
            GridLayout:
                cols: 3
                spacing: dp(8)
                row_default_height: dp(44)
                size_hint_y: None
                height: self.minimum_height
                Button:
                    text: app.tr("Pause", app.language) if not app.root.live_paused else app.tr("Resume", app.language)
                    on_release: app.root.toggle_live_pause()
                Button:
                    text: app.tr("Complete set", app.language)
                    on_release: app.root.manual_complete_set()
                Button:
                    text: app.tr("Skip exercise", app.language)
                    on_release: app.root.skip_current_exercise()
                Button:
                    text: app.tr("Next exercise", app.language)
                    on_release: app.root.manual_next_exercise()
                Button:
                    text: app.tr("End workout", app.language)
                    on_release: app.root.prompt_end_live_session()
                Button:
                    text: app.tr("Back to plan", app.language)
                    on_release: app.root.prompt_go_recommend()
            Widget:
                size_hint_y: None
                height: dp(8)

<HomeScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(20)
        spacing: dp(16)
        Label:
            text: app.tr("Welcome to the Exercise Manager", app.language)
            font_size: "20sp"
            bold: True
            color: 0.12, 0.14, 0.22, 1
            size_hint_y: None
            height: dp(30)
        Label:
            text: app.tr("Choose what you want to do", app.language)
            color: 0.2, 0.2, 0.3, 1
            size_hint_y: None
            height: dp(22)
        WrapLabel:
            text: app.tr("Live Mode: build a plan under Recommend, then press Start.", app.language)
            font_size: "18sp"
            bold: True
            color: 0.16, 0.16, 0.22, 1
            text_size: self.width, None
            halign: "center"
        BoxLayout:
            orientation: "vertical"
            padding: dp(12)
            spacing: dp(8)
            size_hint_y: None
            height: self.minimum_height
            canvas.before:
                Color:
                    rgba: 0.92, 0.97, 1, 1
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [10,]
            Label:
                text: app.tr("Your profile", app.language)
                font_size: "17sp"
                bold: True
                color: 0.12, 0.14, 0.22, 1
                size_hint_y: None
                height: dp(22)
            WrapLabel:
                text: app.tr("Current user: [b]{value}[/b]", app.language, value=app.root.current_user_display)
                markup: True
                font_size: "16sp"
                color: 0.12, 0.14, 0.22, 1
            GridLayout:
                cols: 2
                spacing: dp(8)
                row_default_height: dp(34)
                size_hint_y: None
                height: self.minimum_height
                Label:
                    text: app.tr("Goal", app.language)
                    color: 0.18, 0.18, 0.22, 1
                Spinner:
                    text: app.root.user_profile_goal
                    values: app.root.user_goal_options
                    on_text: app.root.user_profile_goal = self.text
                Label:
                    text: app.tr("Language", app.language)
                    color: 0.18, 0.18, 0.22, 1
                Spinner:
                    text: app.root.language_spinner_text
                    values: app.root.language_options
                    on_text: app.root.on_language_selected(self.text)
            BoxLayout:
                size_hint_y: None
                height: dp(36)
                spacing: dp(8)
                Button:
                    text: app.tr("Save profile", app.language)
                    on_release: app.root.save_user_profile()
            WrapLabel:
                text: app.root.user_profile_status_text
                color: app.root.user_profile_status_color
        AnchorLayout:
            anchor_y: "center"
            BoxLayout:
                orientation: "vertical"
                spacing: dp(12)
                size_hint_y: None
                height: self.minimum_height
                GridLayout:
                    cols: 3
                    spacing: dp(12)
                    row_default_height: dp(70)
                    size_hint_y: None
                    height: self.minimum_height
                    Button:
                        text: app.tr("Browse", app.language)
                        font_size: "26sp"
                        bold: True
                        background_normal: ""
                        background_color: 0.16, 0.6, 0.65, 1
                        color: 1, 1, 1, 1
                        on_release: app.root.go_browse()
                    Button:
                        text: app.tr("Add", app.language)
                        font_size: "26sp"
                        bold: True
                        background_normal: ""
                        background_color: 0.2, 0.45, 0.85, 1
                        color: 1, 1, 1, 1
                        on_release: app.root.go_add()
                    Button:
                        text: app.tr("Users", app.language)
                        font_size: "26sp"
                        bold: True
                        background_normal: ""
                        background_color: 0.9, 0.55, 0.15, 1
                        color: 1, 1, 1, 1
                        on_release: app.root.go_users()
                BoxLayout:
                    size_hint_y: None
                    height: dp(70)
                    spacing: dp(12)
                    Button:
                        text: app.tr("History", app.language)
                        font_size: "26sp"
                        bold: True
                        background_normal: ""
                        background_color: 0.2, 0.65, 0.3, 1
                        color: 1, 1, 1, 1
                        on_release: app.root.go_history()
                    Button:
                        text: app.tr("Recommend", app.language)
                        font_size: "26sp"
                        bold: True
                        background_normal: ""
                        background_color: 0.85, 0.35, 0.25, 1
                        color: 1, 1, 1, 1
                        on_release: app.root.go_recommend()

<BrowseScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(12)
        spacing: dp(10)
        canvas.before:
            Color:
                rgba: 1, 1, 1, 1
            Rectangle:
                pos: self.pos
                size: self.size
        GridLayout:
            cols: 3
            spacing: dp(10)
            size_hint_y: None
            height: self.minimum_height
            padding: dp(12), 0, dp(12), 0
            BoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(4)
                FilterLabel:
                    text: app.tr("Target suitability", app.language)
                Spinner:
                    id: goal_spinner
                    text: app.root.goal_spinner_text
                    values: app.root.goal_options
                    on_text: app.root.on_goal_change(self.text)
                    size_hint_y: None
                    height: dp(36)
                    background_normal: ""
                    background_down: ""
                    background_color: app.root.filter_goal_color
                    color: app.root.filter_goal_text_color
            BoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(4)
                FilterLabel:
                    text: app.tr("Muscle group", app.language)
                Spinner:
                    id: muscle_spinner
                    text: app.root.muscle_spinner_text
                    values: app.root.muscle_options
                    on_text: app.root.on_muscle_change(self.text)
                    size_hint_y: None
                    height: dp(36)
                    background_normal: ""
                    background_down: ""
                    background_color: app.root.filter_muscle_color
                    color: app.root.filter_muscle_text_color
            BoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(4)
                FilterLabel:
                    text: app.tr("Required equipment", app.language)
                Spinner:
                    id: equipment_spinner
                    text: app.root.equipment_spinner_text
                    values: app.root.equipment_options
                    on_text: app.root.on_equipment_change(self.text)
                    size_hint_y: None
                    height: dp(36)
                    background_normal: ""
                    background_down: ""
                    background_color: app.root.filter_equipment_color
                    color: app.root.filter_equipment_text_color
        EmptyStateCard:
            text: app.tr("No exercise currently available for these filters.", app.language) if app.root.browse_empty else ""
        RecycleView:
            id: exercise_list
            viewclass: "ExerciseCard"
            bar_width: dp(6)
            scroll_type: ['bars', 'content']
            RecycleBoxLayout:
                default_size: None, None
                default_size_hint: 1, None
                size_hint_y: None
                height: self.minimum_height
                orientation: "vertical"
                spacing: dp(10)

<AddScreen>:
    ScrollView:
        do_scroll_x: False
        BoxLayout:
            orientation: "vertical"
            padding: dp(12)
            spacing: dp(8)
            size_hint_y: None
            height: self.minimum_height
            canvas.before:
                Color:
                    rgba: 1, 1, 1, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            Label:
                text: app.tr("Add a new exercise", app.language)
                bold: True
                color: 0.12, 0.14, 0.25, 1
                size_hint_y: None
                height: dp(22)
            Label:
                text: app.tr("Defaults: rating 5. Directions required.", app.language)
                color: 0.2, 0.2, 0.28, 1
                size_hint_y: None
                height: dp(20)
            GridLayout:
                cols: 2
                spacing: dp(8)
                row_default_height: dp(34)
                size_hint_y: None
                height: self.minimum_height
                WrapLabel:
                    text: app.tr("Name", app.language)
                    color: 0.18, 0.18, 0.22, 1
                TextInput:
                    id: name_input
                    multiline: False
                    hint_text: app.tr("e.g. Bulgarian Split Squat", app.language)
                WrapLabel:
                    text: app.tr("Description", app.language)
                    color: 0.18, 0.18, 0.22, 1
                TextInput:
                    id: description_input
                    multiline: True
                    size_hint_y: None
                    height: dp(64)
                    hint_text: app.tr("Short overview", app.language)
                WrapLabel:
                    text: app.tr("Execution directions", app.language)
                    color: 0.18, 0.18, 0.22, 1
                TextInput:
                    id: instructions_input
                    multiline: True
                    size_hint_y: None
                    height: dp(90)
                    hint_text: app.tr("Step-by-step directions", app.language)
                WrapLabel:
                    text: app.tr("Muscle group (choose known)", app.language)
                    color: 0.18, 0.18, 0.22, 1
                Spinner:
                    id: muscle_add_spinner
                    text: app.root.add_muscle_spinner_text
                    values: app.root.muscle_choice_options
                    on_text: app.root.add_muscle_spinner_text = self.text
                WrapLabel:
                    text: app.tr("Allowed muscle groups", app.language)
                    color: 0.18, 0.18, 0.22, 1
                Label:
                    text: app.root.muscle_choice_display
                    color: 0.2, 0.2, 0.28, 1
                    text_size: self.width, None
                    size_hint_y: None
                    height: self.texture_size[1]
                WrapLabel:
                    text: app.tr("Required equipment", app.language)
                    color: 0.18, 0.18, 0.22, 1
                Spinner:
                    id: equipment_add_spinner
                    text: app.root.add_equipment_spinner_text
                    values: app.root.equipment_choice_options
                    on_text: app.root.on_add_equipment_change(self.text)
                WrapLabel:
                    text: app.tr("Allowed equipment", app.language)
                    color: 0.18, 0.18, 0.22, 1
                Label:
                    text: app.root.equipment_choice_display
                    color: 0.2, 0.2, 0.28, 1
                    text_size: self.width, None
                    size_hint_y: None
                    height: self.texture_size[1]
                WrapLabel:
                    text: app.tr("Equipment default", app.language)
                    color: 0.18, 0.18, 0.22, 1
                Label:
                    text: app.root.add_equipment_spinner_text or app.tr("Bodyweight", app.language)
                    color: 0.2, 0.2, 0.28, 1
                    size_hint_y: None
                    height: dp(18)
                WrapLabel:
                    text: app.tr("Supports external weight", app.language)
                    color: 0.18, 0.18, 0.22, 1
                Spinner:
                    id: supports_weight_spinner
                    text: app.root.add_supports_weight_spinner_text
                    values: app.root.supports_weight_options
                    on_text: app.root.set_add_supports_weight(self.text)
                WrapLabel:
                    text: app.tr("Default weight (optional)", app.language)
                    color: 0.18, 0.18, 0.22, 1
                    size_hint_y: None
                    height: dp(18) if app.root.add_supports_weight else dp(0)
                    opacity: 1 if app.root.add_supports_weight else 0
                BoxLayout:
                    spacing: dp(6)
                    size_hint_y: None
                    height: dp(34) if app.root.add_supports_weight else dp(0)
                    opacity: 1 if app.root.add_supports_weight else 0
                    TextInput:
                        id: default_weight_input
                        multiline: False
                        input_filter: "float"
                        hint_text: app.tr("e.g. 12.5", app.language)
                        disabled: not app.root.add_supports_weight
                    Label:
                        id: default_weight_unit_spinner
                        text: app.root.add_weight_unit_spinner_text
                        color: 0.2, 0.2, 0.25, 1
                        size_hint_x: None
                        width: dp(32)
                WrapLabel:
                    text: app.tr("Icon (optional)", app.language)
                    color: 0.18, 0.18, 0.22, 1
                Spinner:
                    id: icon_spinner
                    text: app.root.icon_choice_spinner_text
                    values: app.root.icon_choice_options
                    on_text: app.root.on_icon_choice_change(self.text)
                WrapLabel:
                    text: app.tr("Icon preview", app.language)
                    color: 0.18, 0.18, 0.22, 1
                Image:
                    source: app.root.add_icon_source
                    size_hint_y: None
                    height: dp(80) if app.root.add_icon_source else dp(0)
                    fit_mode: "contain"
                    opacity: 1 if app.root.add_icon_source else 0
                WrapLabel:
                    text: app.tr("Target suitability goal", app.language)
                    color: 0.18, 0.18, 0.22, 1
                Spinner:
                    id: goal_add_spinner
                    text: app.root.add_goal_spinner_text
                    values: app.root.goal_choice_options
                    on_text: app.root.add_goal_spinner_text = self.text
                WrapLabel:
                    text: app.tr("Suitability rating (1-10, default 5)", app.language)
                    color: 0.18, 0.18, 0.22, 1
                Spinner:
                    id: rating_spinner
                    text: app.root.rating_spinner_text
                    values: ("1","2","3","4","5","6","7","8","9","10")
                WrapLabel:
                    text: app.tr("Recommended sets (optional, e.g. 3)", app.language)
                    color: 0.18, 0.18, 0.22, 1
                TextInput:
                    id: sets_input
                    multiline: False
                    input_filter: "int"
                    hint_text: app.tr("e.g. 3 (optional)", app.language)
                WrapLabel:
                    text: app.tr("Recommended reps (optional, e.g. 10)", app.language)
                    color: 0.18, 0.18, 0.22, 1
                TextInput:
                    id: reps_input
                    multiline: False
                    input_filter: "int"
                    hint_text: app.tr("e.g. 10 (optional)", app.language)
                WrapLabel:
                    text: app.tr("Recommended time (sec, optional, e.g. 45)", app.language)
                    color: 0.18, 0.18, 0.22, 1
                TextInput:
                    id: time_input
                    multiline: False
                    input_filter: "int"
                    hint_text: app.tr("e.g. 45 (seconds, optional)", app.language)
            BoxLayout:
                size_hint_y: None
                height: dp(40)
                spacing: dp(10)
                Button:
                    text: app.tr("Add Exercise", app.language)
                    on_press: app.root.handle_add_exercise()
            WrapLabel:
                text: app.root.status_text
                color: app.root.status_color

<UserScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(12)
        spacing: dp(10)
        canvas.before:
            Color:
                rgba: 1, 1, 1, 1
            Rectangle:
                pos: self.pos
                size: self.size
        AnchorLayout:
            anchor_y: "center"
            size_hint_y: 0.55
            BoxLayout:
                orientation: "vertical"
                spacing: dp(10)
                size_hint_y: None
                height: self.minimum_height
                WrapLabel:
                    text: app.tr("Select user", app.language)
                    font_size: "18sp"
                    bold: True
                    color: 0.12, 0.14, 0.22, 1
                    text_size: self.width, None
                    halign: "center"
                AnchorLayout:
                    anchor_x: "center"
                    size_hint_y: None
                    height: dp(44)
                    Spinner:
                        id: user_spinner
                        text: app.root.user_spinner_text
                        values: app.root.user_options
                        on_text: app.root.on_user_selected(self.text)
                        size_hint_x: None
                        width: dp(240)
                        text_size: self.size
                        halign: "center"
                        valign: "middle"
                AnchorLayout:
                    anchor_x: "center"
                    size_hint_y: None
                    height: dp(34)
                    BoxLayout:
                        spacing: dp(8)
                        size_hint_x: None
                        width: dp(260)
                        Label:
                            text: app.tr("Language", app.language)
                            color: 0.18, 0.18, 0.22, 1
                            size_hint_x: None
                            width: dp(90)
                        Spinner:
                            text: app.root.language_spinner_text
                            values: app.root.language_options
                            on_text: app.root.on_language_selected(self.text)
                WrapLabel:
                    text: app.tr("Pick a user to get started.", app.language)
                    color: 0.2, 0.2, 0.3, 1
                    text_size: self.width, None
                    halign: "center"
                WrapLabel:
                    text: app.tr("Current user: {value}", app.language, value=app.root.current_user_display)
                    color: 0.2, 0.2, 0.3, 1
                    text_size: self.width, None
                    halign: "center"
                AnchorLayout:
                    anchor_x: "center"
                    size_hint_y: None
                    height: dp(40)
                    Button:
                        text: app.tr("Open history", app.language)
                        size_hint_x: None
                        width: dp(160)
                        on_release: app.root.go_history()
                AnchorLayout:
                    anchor_x: "center"
                    size_hint_y: None
                    height: dp(40)
                    Button:
                        text: app.tr("Delete user", app.language)
                        size_hint_x: None
                        width: dp(160)
                        on_release: app.root.prompt_delete_user()
                Label:
                    text: ""
                    size_hint_y: None
                    height: dp(4)
        AnchorLayout:
            anchor_y: "bottom"
            size_hint_y: 0.45
            BoxLayout:
                orientation: "vertical"
                spacing: dp(8)
                size_hint_y: None
                height: self.minimum_height
                Label:
                    text: app.tr("New here?", app.language)
                    font_size: "17sp"
                    bold: True
                    color: 0.12, 0.14, 0.22, 1
                    size_hint_y: None
                    height: dp(24)
                WrapLabel:
                    text: app.tr("Create a profile with a username and goal.", app.language)
                    color: 0.2, 0.2, 0.3, 1
                    text_size: self.width, None
                    halign: "center"
                AnchorLayout:
                    anchor_x: "center"
                    size_hint_y: None
                    height: dp(40)
                    Button:
                        text: app.tr("Register", app.language)
                        size_hint_x: None
                        width: dp(160)
                        on_release: app.root.go_register()
                WrapLabel:
                    text: app.root.user_status_text
                    color: app.root.user_status_color

<RegisterScreen>:
    AnchorLayout:
        anchor_y: "top"
        canvas.before:
            Color:
                rgba: 1, 1, 1, 1
            Rectangle:
                pos: self.pos
                size: self.size
        BoxLayout:
            orientation: "vertical"
            padding: dp(12), dp(6), dp(12), dp(12)
            spacing: dp(10)
            size_hint_y: None
            height: self.minimum_height
            Label:
                text: app.tr("Register new user", app.language)
                font_size: "18sp"
                bold: True
                color: 0.12, 0.14, 0.22, 1
                size_hint_y: None
                height: dp(26)
            WrapLabel:
                text: app.tr("Set a username and choose a goal to get started.", app.language)
                color: 0.2, 0.2, 0.3, 1
            GridLayout:
                cols: 2
                spacing: dp(8)
                row_default_height: dp(34)
                size_hint_y: None
                height: self.minimum_height
                WrapLabel:
                    text: app.tr("Username", app.language)
                    color: 0.18, 0.18, 0.22, 1
                TextInput:
                    id: register_username_input
                    hint_text: app.tr("e.g. alex", app.language)
                    multiline: False
                WrapLabel:
                    text: app.tr("Display name (optional)", app.language)
                    color: 0.18, 0.18, 0.22, 1
                TextInput:
                    id: register_display_input
                    hint_text: app.tr("Name shown in app", app.language)
                    multiline: False
                WrapLabel:
                    text: app.tr("Goal", app.language)
                    color: 0.18, 0.18, 0.22, 1
                Spinner:
                    id: register_goal_spinner
                    text: app.root.register_goal_spinner_text
                    values: app.root.user_goal_options
                    on_text: app.root.register_goal_spinner_text = self.text
            WrapLabel:
                text: app.root.register_status_text
                color: app.root.register_status_color
            BoxLayout:
                size_hint_y: None
                height: dp(40)
                spacing: dp(8)
                Button:
                    text: app.tr("Register", app.language)
                    on_release: app.root.handle_register_user()
                Button:
                    text: app.tr("Cancel", app.language)
                    on_release: app.root.go_users()

<HistoryScreen>:
    ScrollView:
        do_scroll_x: False
        BoxLayout:
            orientation: "vertical"
            padding: dp(12)
            spacing: dp(10)
            size_hint_y: None
            height: self.minimum_height
            canvas.before:
                Color:
                    rgba: 1, 1, 1, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            Label:
                text: app.tr("Workout history", app.language)
                font_size: "18sp"
                bold: True
                color: 0.12, 0.14, 0.22, 1
                size_hint_y: None
                height: dp(26)
            WrapLabel:
                text: app.tr("Current user: {value}", app.language, value=app.root.current_user_display)
                color: 0.2, 0.2, 0.3, 1
            GridLayout:
                cols: 2
                spacing: dp(8)
                row_default_height: dp(34)
                size_hint_y: None
                height: self.minimum_height
                WrapLabel:
                    text: app.tr("Start date (YYYY-MM-DD)", app.language)
                    color: 0.18, 0.18, 0.22, 1
                BoxLayout:
                    spacing: dp(6)
                    TextInput:
                        id: start_date_input
                        multiline: False
                        readonly: True
                        hint_text: app.tr("optional", app.language)
                    Button:
                        text: app.tr("Pick", app.language)
                        size_hint_x: None
                        width: dp(70)
                        on_release: app.root.open_date_picker(start_date_input)
                WrapLabel:
                    text: app.tr("End date (YYYY-MM-DD)", app.language)
                    color: 0.18, 0.18, 0.22, 1
                BoxLayout:
                    spacing: dp(6)
                    TextInput:
                        id: end_date_input
                        multiline: False
                        readonly: True
                        hint_text: app.tr("optional", app.language)
                    Button:
                        text: app.tr("Pick", app.language)
                        size_hint_x: None
                        width: dp(70)
                        on_release: app.root.open_date_picker(end_date_input)
            BoxLayout:
                size_hint_y: None
                height: dp(40)
                spacing: dp(10)
                padding: dp(12), 0, dp(12), 0
                Button:
                    text: app.tr("Clear filter", app.language)
                    size_hint_x: None
                    width: dp(150)
                    on_release: app.root.clear_history_filter()
            BoxLayout:
                orientation: "vertical"
                size_hint_y: None
                height: self.minimum_height
                padding: dp(12)
                spacing: dp(6)
                canvas.before:
                    Color:
                        rgba: 0.93, 0.96, 1, 1
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [10,]
                Label:
                    text: app.tr("Stats", app.language)
                    bold: True
                    font_size: "16sp"
                    color: 0.12, 0.14, 0.22, 1
                    size_hint_y: None
                    height: dp(22)
                Label:
                    text: app.tr("Total workouts: [b]{value}[/b]", app.language, value=app.root.stats_total_workouts)
                    markup: True
                    font_size: "15sp"
                    color: 0.16, 0.18, 0.26, 1
                    text_size: self.width, None
                    halign: "left"
                    size_hint_y: None
                    height: dp(20)
                Label:
                    text: app.tr("Total time: [b]{value} min[/b]", app.language, value=app.root.stats_total_minutes)
                    markup: True
                    font_size: "15sp"
                    color: 0.16, 0.18, 0.26, 1
                    text_size: self.width, None
                    halign: "left"
                    size_hint_y: None
                    height: dp(20)
                Label:
                    text: app.tr("Total load: [b]{value}[/b]", app.language, value=app.root.stats_total_weight)
                    markup: True
                    font_size: "15sp"
                    color: 0.16, 0.18, 0.26, 1
                    text_size: self.width, None
                    halign: "left"
                    size_hint_y: None
                    height: dp(20)
                Label:
                    text: app.tr("Top exercise: [b]{value}[/b]", app.language, value=app.root.stats_top_exercise)
                    markup: True
                    font_size: "15sp"
                    color: 0.16, 0.18, 0.26, 1
                    text_size: self.width, None
                    halign: "left"
                    size_hint_y: None
                    height: dp(20)
            BoxLayout:
                size_hint_y: None
                height: dp(40)
                spacing: dp(10)
                padding: dp(12), 0, dp(12), 0
                Button:
                    text: app.tr("Log a completed workout", app.language)
                    size_hint_x: None
                    width: dp(220)
                    on_release: app.root.open_workout_log_modal()
                Button:
                    text: app.tr("Refresh history", app.language)
                    size_hint_x: None
                    width: dp(180)
                    on_release: app.root._load_history()
            WrapLabel:
                text: app.root.history_status_text
                color: app.root.history_status_color
                font_size: app.root.history_status_font_size
            BoxLayout:
                id: history_list
                orientation: "vertical"
                spacing: dp(12)
                size_hint_y: None
                height: self.minimum_height

<RecommendationScreen>:
    BoxLayout:
        orientation: "vertical"
        padding: dp(12)
        spacing: dp(10)
        canvas.before:
            Color:
                rgba: 1, 1, 1, 1
            Rectangle:
                pos: self.pos
                size: self.size
        GridLayout:
            cols: 2
            spacing: dp(8)
            row_default_height: dp(34)
            size_hint_y: None
            height: self.minimum_height
            WrapLabel:
                text: app.tr("Goal", app.language)
                color: 0.18, 0.18, 0.22, 1
            Spinner:
                id: rec_goal_spinner
                text: app.root.rec_goal_spinner_text
                values: app.root.goal_choice_options
                on_text: app.root.rec_goal_spinner_text = self.text
            WrapLabel:
                text: app.tr("Max time (minutes)", app.language)
                color: 0.18, 0.18, 0.22, 1
            TextInput:
                id: rec_max_time
                text: app.root.rec_max_minutes_text
                multiline: False
                input_filter: "int"
                on_text: app.root.on_rec_max_time_change(self.text)
        BoxLayout:
            size_hint_y: None
            height: dp(40)
            spacing: dp(8)
            Button:
                text: app.tr("Clear plan", app.language)
                on_release: app.root.clear_recommendation_plan()
            Button:
                text: app.tr("Generate recommendations", app.language)
                on_release: app.root.handle_generate_recommendations()
        StatusBanner:
            text: app.root.rec_status_text
            status_color: app.root.rec_status_color
            is_error: app.root.rec_status_is_error
        Label:
            text: app.tr("Recommended exercises", app.language)
            bold: True
            color: 0.12, 0.14, 0.22, 1
            size_hint_y: None
            height: dp(22)
        RecycleView:
            id: rec_list
            viewclass: "RecommendationCard"
            bar_width: dp(6)
            scroll_type: ['bars', 'content']
            size_hint_y: 1
            RecycleGridLayout:
                cols: 2
                default_size: None, dp(240)
                default_size_hint: 0.5, None
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(10)
        WrapLabel:
            text: app.tr("Add your first exercise to get started.", app.language) if not app.root.rec_plan else app.tr("Your training plan (reorder with Up/Down)", app.language)
            bold: False if not app.root.rec_plan else True
            color: (0.35, 0.35, 0.4, 1) if not app.root.rec_plan else (0.12, 0.14, 0.22, 1)
        RecycleView:
            id: rec_plan_list
            viewclass: "PlanItem"
            bar_width: dp(6)
            scroll_type: ['bars', 'content']
            size_hint_y: None
            height: app.root.rec_plan_height
            RecycleBoxLayout:
                default_size: None, dp(92)
                default_size_hint: 1, None
                size_hint_y: None
                height: self.minimum_height
                orientation: "vertical"
                spacing: dp(6)
        BoxLayout:
            size_hint_y: None
            height: dp(36)
            spacing: dp(8)
            Label:
                text: app.tr("Total time: {current} / {max} min", app.language, current=app.root.rec_total_minutes, max=app.root.rec_max_minutes_text or "0")
                color: 0.18, 0.18, 0.24, 1
            Button:
                text: app.tr("Start training", app.language)
                on_release: app.root.handle_start_training()

<SummaryScreen>:
    ScrollView:
        do_scroll_x: False
        BoxLayout:
            orientation: "vertical"
            padding: dp(14)
            spacing: dp(10)
            size_hint_y: None
            height: self.minimum_height
            canvas.before:
                Color:
                    rgba: 1, 1, 1, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
            Label:
                text: app.tr("Workout summary", app.language)
                font_size: "20sp"
                bold: True
                color: 0.1, 0.12, 0.2, 1
                size_hint_y: None
                height: dp(28)
            GridLayout:
                cols: 2
                spacing: dp(8)
                row_default_height: dp(26)
                size_hint_y: None
                height: self.minimum_height
                Label:
                    text: app.tr("Finished at", app.language)
                    color: 0.18, 0.18, 0.22, 1
                WrapLabel:
                    text: app.root.summary_performed_at_display
                    color: 0.16, 0.2, 0.3, 1
                    halign: "left"
                Label:
                    text: app.tr("Goal", app.language)
                    color: 0.18, 0.18, 0.22, 1
                WrapLabel:
                    text: app.root.summary_goal_display
                    color: 0.16, 0.2, 0.3, 1
                Label:
                    text: app.tr("Total duration", app.language)
                    color: 0.18, 0.18, 0.22, 1
                WrapLabel:
                    text: app.root.summary_duration_display
                    color: 0.16, 0.2, 0.3, 1
                Label:
                    text: app.tr("Completed sets", app.language)
                    color: 0.18, 0.18, 0.22, 1
                WrapLabel:
                    text: app.root.summary_sets_display
                    color: 0.16, 0.2, 0.3, 1
            Label:
                text: app.tr("Completed exercises: {value}", app.language, value=app.root.summary_completed_display)
                color: 0.15, 0.18, 0.26, 1
                text_size: self.width, None
                size_hint_y: None
                height: self.texture_size[1]
            Label:
                text: app.tr("Skipped exercises: {value}", app.language, value=app.root.summary_skipped_display)
                color: 0.2, 0.16, 0.18, 1
                text_size: self.width, None
                size_hint_y: None
                height: self.texture_size[1]
            Label:
                text: app.tr("Attempted exercises with status:", app.language)
                bold: True
                color: 0.12, 0.14, 0.22, 1
                size_hint_y: None
                height: dp(22)
            Label:
                text: app.root.summary_attempts_display
                color: 0.16, 0.2, 0.3, 1
                text_size: self.width, None
                size_hint_y: None
                height: self.texture_size[1]
            BoxLayout:
                size_hint_y: None
                height: dp(44)
                spacing: dp(10)
                Button:
                    text: app.tr("Return to main menu", app.language)
                    on_release: app.root.go_home()
                Button:
                    text: app.tr("Start a new training session", app.language)
                    on_release: app.root.start_new_session()
<RootWidget>:
    orientation: "vertical"
    canvas.before:
        Color:
            rgba: 1, 1, 1, 1
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        size_hint_y: None
        height: dp(50)
        padding: dp(10), dp(6)
        spacing: dp(10)
        canvas.before:
            Color:
                rgba: 0.94, 0.96, 0.99, 1
            Rectangle:
                pos: self.pos
                size: self.size
        Label:
            text: app.tr("Exercise Manager", app.language)
            font_size: "18sp"
            bold: True
            color: 0.1, 0.12, 0.2, 1
            size_hint_x: None
            width: self.texture_size[0] + dp(14)
        ScrollView:
            do_scroll_y: False
            bar_width: dp(0)
            size_hint_x: 1
            BoxLayout:
                size_hint_x: None
                width: self.minimum_width
                spacing: dp(10)
                NavButton:
                    text: app.tr("Home", app.language)
                    size_hint_x: None
                    width: dp(90)
                    on_release: root.go_home()
                NavButton:
                    text: app.tr("Browse", app.language)
                    size_hint_x: None
                    width: dp(90)
                    on_release: root.go_browse()
                NavButton:
                    text: app.tr("Add", app.language)
                    size_hint_x: None
                    width: dp(90)
                    on_release: root.go_add()
                NavButton:
                    text: app.tr("Users", app.language)
                    size_hint_x: None
                    width: dp(90)
                    on_release: root.go_users()
                NavButton:
                    text: app.tr("History", app.language)
                    size_hint_x: None
                    width: dp(90)
                    on_release: root.go_history()
                NavButton:
                    text: app.tr("Recommend", app.language)
                    size_hint_x: None
                    width: dp(110)
                    on_release: root.go_recommend()
                NavButton:
                    text: app.tr("Live", app.language)
                    size_hint_x: None
                    width: dp(90)
                    disabled: not app.root.live_active
                    on_release: root.go_live()

    ScreenManager:
        id: screen_manager
        HomeScreen:
            name: "home"
        BrowseScreen:
            name: "browse"
        AddScreen:
            name: "add"
        UserScreen:
            name: "user"
        RegisterScreen:
            name: "register"
        HistoryScreen:
            name: "history"
        RecommendationScreen:
            name: "recommend"
        LiveScreen:
            name: "live"
        SummaryScreen:
            name: "summary"
"""

ALL_FILTER = "__all__"


class ExerciseCard(ButtonBehavior, BoxLayout):
    """Card widget that displays exercise details in browse lists."""
    # Kivy properties bound by the KV layout for exercise cards.
    name = StringProperty()
    display_name = StringProperty()
    icon_source = StringProperty("")
    description = StringProperty()
    execution_instructions = StringProperty()
    goal_label = StringProperty()
    muscle_group = StringProperty()
    equipment = StringProperty()
    suitability_display = StringProperty()
    suitability_value = StringProperty()
    estimated_minutes = StringProperty()
    score_display = StringProperty()
    recommendation = StringProperty()
    sets_display = StringProperty("—")
    reps_display = StringProperty("—")
    time_display = StringProperty("—")


class DetailRow(BoxLayout):
    """Row widget for labeled detail values."""
    label_text = StringProperty("")
    value_text = StringProperty("")


class HomeScreen(Screen):
    """Landing screen that routes users to major app areas."""
    # Marker class for ScreenManager routing.
    pass


class BrowseScreen(Screen):
    """Screen for filtering and browsing exercises."""
    # Marker class for ScreenManager routing.
    pass


class AddScreen(Screen):
    """Screen for adding new exercises to the database."""
    # Marker class for ScreenManager routing.
    pass


class UserScreen(Screen):
    """Screen for selecting or creating user profiles."""
    # Marker class for ScreenManager routing.
    pass


class RegisterScreen(Screen):
    """Screen for registering a new user profile."""
    # Marker class for ScreenManager routing.
    pass


class HistoryScreen(Screen):
    """Screen for viewing and filtering workout history."""
    # Marker class for ScreenManager routing.
    pass


class WorkoutCard(BoxLayout):
    """Card widget that summarizes a logged workout."""
    # Kivy properties bound by the workout history list.
    date_display = StringProperty()
    duration_display = StringProperty()
    exercises_display = StringProperty()
    goal_display = StringProperty()
    sets_display = StringProperty()
    attempts_display = StringProperty()


class RecommendationScreen(Screen):
    """Screen that shows recommendations and a workout plan."""
    # Marker class for ScreenManager routing.
    pass


class LiveScreen(Screen):
    """Screen that runs a live workout session."""
    # Marker class for ScreenManager routing.
    pass


class SummaryScreen(Screen):
    """Screen that summarizes a finished workout session."""
    # Marker class for ScreenManager routing.
    pass


class PlanItem(BoxLayout):
    """List row representing a planned recommendation."""
    # Kivy properties bound by the plan list view.
    name = StringProperty()
    icon_source = StringProperty("")
    display = StringProperty()
    index = StringProperty()
    weight_value_text = StringProperty("")
    weight_unit_text = StringProperty("kg")
    weight_visible = BooleanProperty(False)
    pass


class ProgressRing(Widget):
    """Canvas widget that renders a circular progress ring."""
    # Kivy properties used by the KV canvas instructions.
    progress = NumericProperty(0.0)
    thickness = NumericProperty(6.0)
    color = ListProperty((0.18, 0.4, 0.85, 1))
    background_color = ListProperty((0.86, 0.9, 0.96, 1))


class RecommendationCard(BoxLayout):
    """Card widget that presents a recommended exercise."""
    # Kivy properties bound by recommendation list entries.
    name = StringProperty()
    display_name = StringProperty()
    icon_source = StringProperty("")
    description = StringProperty()
    execution_instructions = StringProperty()
    muscle_group = StringProperty()
    equipment = StringProperty()
    suitability = StringProperty()
    estimated_minutes = StringProperty()
    score_display = StringProperty()
    recommendation = StringProperty()
    show_details = BooleanProperty(False)


class DatePickerPopup(ModalView):
    """Modal date picker used by history and workout log forms."""
    # Kivy properties that track selected date state.
    month_label = StringProperty("")
    selected_label = StringProperty("")

    def __init__(self, *, on_select, initial_date: Optional[date] = None, **kwargs):
        """Initialize the popup with an optional initial date and callback."""
        # Initialize selection state and build the calendar UI.
        super().__init__(**kwargs)
        self._on_select = on_select
        chosen = initial_date or date.today()
        self._selected_date = chosen
        self.selected_label = chosen.isoformat()
        self._shown_year = chosen.year
        self._shown_month = chosen.month
        self.month_label = localization.format_month_year(
            self._shown_year,
            self._shown_month,
            self._current_language(),
        )
        Clock.schedule_once(self._populate_calendar, 0)

    def _current_language(self) -> str:
        """Return the active language code."""
        app = App.get_running_app()
        if app and getattr(app, "language", None):
            return app.language
        return localization.DEFAULT_LANGUAGE

    def shift_month(self, delta: int) -> None:
        """Move the calendar view by the requested number of months."""
        # Delegate to the month shift helper.
        self._change_months(delta)

    def shift_year(self, delta_years: int) -> None:
        """Move the calendar view by the requested number of years."""
        # Convert years to months for the shared handler.
        self._change_months(delta_years * 12)

    def confirm_selection(self) -> None:
        """Commit the selected date and close the popup."""
        # Notify the caller before dismissing the modal.
        selected = self._selected_date or date.today()
        if self._on_select:
            self._on_select(selected)
        self.dismiss()

    def select_today(self) -> None:
        """Jump to today and confirm it."""
        # Ensure today is highlighted and selected.
        today = date.today()
        self._set_selected_date(today, update_month=True)
        self.confirm_selection()

    def _set_selected_date(self, selected: date, *, update_month: bool = False) -> None:
        """Update the selected date and rebuild the calendar grid."""
        # Keep the label and month view in sync with selection changes.
        self._selected_date = selected
        self.selected_label = selected.isoformat()
        if update_month:
            self._shown_year = selected.year
            self._shown_month = selected.month
            self.month_label = localization.format_month_year(
                self._shown_year,
                self._shown_month,
                self._current_language(),
            )
        self._populate_calendar()

    def _set_selected_day(self, day: int, *_: Any) -> None:
        """Handle day button selection from the calendar grid."""
        # Build a date from the shown month and day.
        selected = date(self._shown_year, self._shown_month, day)
        self._set_selected_date(selected)

    def _change_months(self, delta_months: int) -> None:
        """Adjust the shown month by a delta and refresh labels."""
        # Clamp negative values so calendar math stays valid.
        total_months = (self._shown_year * 12 + (self._shown_month - 1)) + delta_months
        if total_months < 0:
            total_months = 0
        new_year, month_index = divmod(total_months, 12)
        self._shown_year = new_year
        self._shown_month = month_index + 1
        self.month_label = localization.format_month_year(
            self._shown_year,
            self._shown_month,
            self._current_language(),
        )
        self._populate_calendar()

    def _populate_calendar(self, *_: Any) -> None:
        """Render weekday headers and day buttons for the current month."""
        # Rebuild the grid every time the month or selection changes.
        if not self.ids:
            return
        grid = self.ids.day_grid
        grid.clear_widgets()
        for weekday in localization.weekday_labels(self._current_language()):
            grid.add_widget(
                Label(
                    text=weekday,
                    bold=True,
                    font_size="12sp",
                    color=(0.15, 0.18, 0.25, 1),
                    halign="center",
                    valign="middle",
                    text_size=(dp(40), dp(32)),
                )
            )
        today = date.today()
        selected = self._selected_date
        month_days = calendar.Calendar(firstweekday=0).monthdayscalendar(self._shown_year, self._shown_month)
        for week in month_days:
            for day in week:
                if day == 0:
                    grid.add_widget(Label(text=""))
                else:
                    is_today = (
                        today.year == self._shown_year
                        and today.month == self._shown_month
                        and today.day == day
                    )
                    is_selected = (
                        selected
                        and selected.year == self._shown_year
                        and selected.month == self._shown_month
                        and selected.day == day
                    )
                    if is_selected:
                        background_color = (0.18, 0.4, 0.85, 1)
                        text_color = (1, 1, 1, 1)
                    elif is_today:
                        background_color = (0.85, 0.92, 1, 1)
                        text_color = (0.12, 0.14, 0.22, 1)
                    else:
                        background_color = (0.94, 0.96, 1, 1)
                        text_color = (0.14, 0.16, 0.24, 1)
                    grid.add_widget(
                        Button(
                            text=str(day),
                            font_size="14sp",
                            background_normal="",
                            background_down="",
                            background_color=background_color,
                            color=text_color,
                            on_release=partial(self._set_selected_day, day),
                        )
                    )


class ConfirmActionModal(ModalView):
    """Modal prompt for confirming live mode actions."""
    message = StringProperty("")
    confirm_label = StringProperty("Confirm")
    cancel_label = StringProperty("Cancel")


class DeleteUserModal(ModalView):
    """Modal prompt for selecting a user to delete."""
    # KV handles the layout; this class is a hook for bindings.
    pass


class WorkoutLogModal(ModalView):
    """Modal form for logging completed workouts."""
    # KV handles the layout; this class is a hook for bindings.
    pass


class GoalPromptModal(ModalView):
    """Modal prompt for setting a user goal."""
    # KV handles the layout; this class is a hook for bindings.
    pass


class ExerciseDetailsModal(ModalView):
    """Modal showing detailed information for one exercise."""
    # Kivy properties bound by the detail template.
    exercise_name = StringProperty("")
    exercise_key = StringProperty("")
    description = StringProperty("")
    execution_instructions = StringProperty("")
    muscle_group = StringProperty("")
    equipment = StringProperty("")
    goal_label = StringProperty("")
    suitability = StringProperty("")
    estimated_minutes = StringProperty("")
    score_display = StringProperty("")
    recommendation = StringProperty("")
    sets_display = StringProperty("—")
    reps_display = StringProperty("—")
    time_display = StringProperty("—")
    show_add_button = BooleanProperty(False)


class FutureDateError(ValueError):
    """Error raised when a workout date is set in the future."""
    pass


class RootWidget(BoxLayout):
    """Main application controller and data/state hub."""
    # Centralized Kivy properties that drive the UI bindings.
    goal_options = ListProperty()
    goal_choice_options = ListProperty()
    muscle_choice_options = ListProperty()
    equipment_choice_options = ListProperty()
    muscle_options = ListProperty()
    equipment_options = ListProperty()
    user_options = ListProperty()
    user_goal_options = ListProperty()
    history_exercise_options = ListProperty()
    history_exercise_filtered_options = ListProperty()
    workout_goal_options = ListProperty()
    icon_choice_options = ListProperty()
    language_options = ListProperty()
    language_spinner_text = StringProperty("")
    supports_weight_options = ListProperty()
    weight_unit_options = ListProperty(["kg"])
    _goal_weight_multipliers = {
        "muscle_building": 1.0,
        "weight_loss": 0.85,
        "strength_increase": 1.15,
        "endurance_increase": 0.7,
    }

    goal_spinner_text = StringProperty("")
    muscle_spinner_text = StringProperty("")
    equipment_spinner_text = StringProperty("")
    filter_goal_color = ListProperty((0.93, 0.95, 0.98, 1))
    filter_goal_text_color = ListProperty((0.2, 0.2, 0.25, 1))
    filter_muscle_color = ListProperty((0.93, 0.95, 0.98, 1))
    filter_muscle_text_color = ListProperty((0.2, 0.2, 0.25, 1))
    filter_equipment_color = ListProperty((0.93, 0.95, 0.98, 1))
    filter_equipment_text_color = ListProperty((0.2, 0.2, 0.25, 1))
    add_goal_spinner_text = StringProperty("")
    add_muscle_spinner_text = StringProperty("")
    add_equipment_spinner_text = StringProperty("")
    add_supports_weight = BooleanProperty(False)
    add_supports_weight_spinner_text = StringProperty("")
    add_weight_unit_spinner_text = StringProperty("kg")
    rating_spinner_text = StringProperty("5")
    icon_choice_spinner_text = StringProperty("")
    history_exercise_spinner_text = StringProperty("")
    workout_goal_spinner_text = StringProperty("")
    history_exercise_filter = StringProperty("")
    history_weight_visible = BooleanProperty(False)

    filter_goal = StringProperty(ALL_FILTER)
    filter_muscle_group = StringProperty(ALL_FILTER)
    filter_equipment = StringProperty(ALL_FILTER)
    status_text = StringProperty("")
    status_color = ListProperty((0.14, 0.4, 0.2, 1))
    muscle_choice_display = StringProperty("")
    equipment_choice_display = StringProperty("")
    add_icon_source = StringProperty("")
    user_spinner_text = StringProperty("")
    delete_user_spinner_text = StringProperty("")
    delete_user_ready = BooleanProperty(False)
    current_user_display = StringProperty("")
    user_status_text = StringProperty("")
    user_status_color = ListProperty((0.14, 0.4, 0.2, 1))
    register_goal_spinner_text = StringProperty("")
    register_status_text = StringProperty("")
    register_status_color = ListProperty((0.14, 0.4, 0.2, 1))
    user_profile_name = StringProperty("")
    user_profile_goal = StringProperty("")
    user_profile_status_text = StringProperty("")
    user_profile_status_color = ListProperty((0.14, 0.4, 0.2, 1))
    history_status_text = StringProperty("")
    history_status_color = ListProperty((0.14, 0.4, 0.2, 1))
    history_status_font_size = StringProperty("15sp")
    stats_total_workouts = StringProperty("0")
    stats_total_minutes = StringProperty("0")
    stats_total_weight = StringProperty("—")
    stats_top_exercise = StringProperty("—")
    rec_status_text = StringProperty("")
    rec_status_color = ListProperty((0.14, 0.4, 0.2, 1))
    rec_status_is_error = BooleanProperty(False)
    rec_goal_spinner_text = StringProperty("")
    rec_max_minutes_text = StringProperty("30")
    rec_recommendations = ListProperty()
    rec_plan = ListProperty()
    rec_total_minutes = StringProperty("0")
    rec_plan_height = NumericProperty(dp(70))
    browse_empty = BooleanProperty(False)
    live_active = BooleanProperty(False)
    live_paused = BooleanProperty(False)
    live_started = BooleanProperty(False)
    live_exercises = ListProperty()
    live_progress_display = StringProperty("")
    live_state_display = StringProperty("")
    live_exercise_title = StringProperty("")
    live_icon_display = StringProperty("")
    live_icon_source = StringProperty("")
    live_muscle_display = StringProperty("")
    live_equipment_display = StringProperty("")
    live_recommendation_display = StringProperty("")
    live_exercise_description = StringProperty("")
    live_exercise_instructions = StringProperty("")
    live_details_expanded = BooleanProperty(False)
    live_exercise_target_display = StringProperty("")
    live_set_target_display = StringProperty("")
    live_reps_display = StringProperty("")
    live_reps_visible = BooleanProperty(False)
    live_set_counter_display = StringProperty("")
    live_rest_setting_text = StringProperty("30")
    live_weight_value_text = StringProperty("")
    live_weight_unit_text = StringProperty("kg")
    live_weight_visible = BooleanProperty(False)
    live_exercise_timer = StringProperty("00:00")
    live_set_timer = StringProperty("00:00")
    live_rest_timer = StringProperty("")
    live_current_set_display = StringProperty("")
    live_exercise_progress = NumericProperty(0.0)
    live_progress_timer = StringProperty("00:00")
    live_progress_color = ListProperty((0.18, 0.4, 0.85, 1))
    live_instruction = StringProperty("")
    live_tempo_hint = StringProperty("")
    live_hint_text = StringProperty("")
    live_hint_color = ListProperty((0.14, 0.4, 0.2, 1))
    live_signal_text = StringProperty("")
    live_signal_color = ListProperty((0.16, 0.32, 0.6, 1))
    live_upcoming_display = StringProperty("")
    summary_duration_display = StringProperty("00:00")
    summary_sets_display = StringProperty("0")
    summary_completed_display = StringProperty("")
    summary_skipped_display = StringProperty("")
    summary_attempts_display = StringProperty("")
    summary_goal_display = StringProperty("")
    summary_performed_at_display = StringProperty("")

    def __init__(self, **kwargs):
        """Initialize UI state, caches, and launch data loading."""
        # Prepare app-level state before KV bindings fire.
        app = App.get_running_app()
        # Ensure app.root is available during KV evaluation to avoid NoneType errors.
        if app and app.root is None:
            app.root = self
        super().__init__(**kwargs)
        self._initializing = True
        self.records: list[dict[str, Any]] = []
        self._users: list[dict[str, Any]] = []
        self.current_user_id: Optional[int] = None
        self.history_start: Optional[str] = None
        self.history_end: Optional[str] = None
        self._goal_label_map: dict[str, str] = {}
        self._goal_code_label_map: dict[str, str] = {}
        self._exercise_display_to_key: dict[str, str] = {}
        self._exercise_key_to_display: dict[str, str] = {}
        self._muscle_display_to_key: dict[str, str] = {}
        self._muscle_key_to_display: dict[str, str] = {}
        self._equipment_display_to_key: dict[str, str] = {}
        self._equipment_key_to_display: dict[str, str] = {}
        self._workout_log_modal: Optional[WorkoutLogModal] = None
        self._goal_prompt_modal: Optional[GoalPromptModal] = None
        self._recommendation_detail_modal: Optional[ExerciseDetailsModal] = None
        self._browse_detail_modal: Optional[ExerciseDetailsModal] = None
        self._confirm_action_modal: Optional[ConfirmActionModal] = None
        self._confirm_action_callback: Optional[Callable[[], None]] = None
        self._delete_user_modal: Optional[DeleteUserModal] = None
        self._pending_delete_user_id: Optional[int] = None
        self._pending_delete_username = ""
        self._history_weight_values: dict[str, dict[str, str]] = {}
        self._live_clock = None
        self._live_current_index = 0
        self._live_current_set = 1
        self._live_set_elapsed = 0.0
        self._live_exercise_elapsed = 0.0
        self._live_rest_remaining = 0.0
        self._live_set_target_seconds = 0.0
        self._live_session_started_at: Optional[datetime] = None
        self._live_completed: list[str] = []
        self._live_skipped: list[str] = []
        self._live_attempt_log: list[dict[str, Any]] = []
        self._live_goal_label: str = ""
        self._live_total_sets_completed = 0
        self._live_current_logged = False
        self.live_rest_seconds = 30
        self.live_rest_setting_text = str(int(self.live_rest_seconds))
        self._apply_language_defaults()
        self._rebuild_goal_maps()
        self._icon_lookup = self._build_icon_lookup()
        self.icon_choice_options = self._build_icon_choice_options()
        if self.icon_choice_spinner_text not in self.icon_choice_options:
            self.icon_choice_spinner_text = self._no_icon_label
        self.on_icon_choice_change(self.icon_choice_spinner_text)
        self._signal_clear_event = None
        self._live_phase = "idle"
        self._update_rec_plan_height()
        Clock.schedule_once(self._bootstrap_data, 0)
        self._initializing = False

    def _current_language(self) -> str:
        """Return the active language code."""
        app = App.get_running_app()
        if app and getattr(app, "language", None):
            return app.language
        return localization.DEFAULT_LANGUAGE

    def _t(self, text: str, **kwargs: Any) -> str:
        """Translate UI text for the active language."""
        return localization.translate(text, self._current_language(), **kwargs)

    def _apply_language_defaults(self) -> None:
        """Set translated defaults for shared labels and options."""
        self._all_goals_label = self._t("All goals")
        self._all_muscle_groups_label = self._t("All muscle groups")
        self._all_equipment_label = self._t("All equipment")
        self._no_goal_label = self._t("No goal")
        self._select_user_label = self._t("Select user")
        self._no_user_label = self._t("No user selected")
        self._no_icon_label = self._t("No icon")
        self._select_icon_label = self._t("Select icon")
        self._no_icons_label = self._t("No icons found")
        self._select_exercise_label = self._t("Select exercise")
        self._no_matches_label = self._t("No matches")
        self._no_exercises_label = self._t("No exercises")
        self._none_label = self._t("None")
        self.supports_weight_options = [self._t("No"), self._t("Yes")]
        self.language_options = list(localization.LANGUAGE_LABELS.values())
        self.language_spinner_text = localization.LANGUAGE_LABELS.get(
            self._current_language(),
            localization.LANGUAGE_LABELS[localization.DEFAULT_LANGUAGE],
        )
        if not self.goal_spinner_text:
            self.goal_spinner_text = self._all_goals_label
        if not self.muscle_spinner_text:
            self.muscle_spinner_text = self._all_muscle_groups_label
        if not self.equipment_spinner_text:
            self.equipment_spinner_text = self._all_equipment_label
        if not self.workout_goal_spinner_text:
            self.workout_goal_spinner_text = self._no_goal_label
        if not self.history_exercise_spinner_text:
            self.history_exercise_spinner_text = self._select_exercise_label
        if not self.user_spinner_text:
            self.user_spinner_text = self._select_user_label
        if not self.delete_user_spinner_text:
            self.delete_user_spinner_text = self._select_user_label
        if not self.current_user_display:
            self.current_user_display = self._no_user_label
        if not self.register_goal_spinner_text:
            self.register_goal_spinner_text = self._no_goal_label
        if not self.user_profile_goal:
            self.user_profile_goal = self._no_goal_label
        if not self.add_supports_weight_spinner_text:
            self.add_supports_weight_spinner_text = self._t("Yes") if self.add_supports_weight else self._t("No")
        if not self.icon_choice_spinner_text:
            self.icon_choice_spinner_text = self._no_icon_label
        if not self.live_progress_display:
            self.live_progress_display = self._t("No session running")
        if not self.live_state_display:
            self.live_state_display = self._t("Not started")
        if not self.live_exercise_title:
            self.live_exercise_title = self._t("No exercise running")
        if not self.live_exercise_target_display:
            self.live_exercise_target_display = "—"
        if not self.live_set_target_display:
            self.live_set_target_display = "—"
        if not self.live_rest_timer:
            self.live_rest_timer = "—"
        if not self.live_upcoming_display:
            self.live_upcoming_display = self._none_label
        if self.summary_completed_display == "":
            self.summary_completed_display = self._none_label
        if self.summary_skipped_display == "":
            self.summary_skipped_display = self._none_label
        if not self.summary_goal_display:
            self.summary_goal_display = "—"

    def _rebuild_goal_maps(self) -> None:
        """Refresh localized goal label maps for the active language."""
        self._goal_label_map = {self._pretty_goal(goal): goal for goal in exercise_database.GOALS}
        self._goal_code_label_map = {goal: self._pretty_goal(goal) for goal in exercise_database.GOALS}

    def _pretty_goal(self, goal: str) -> str:
        """Return a title-cased goal label for UI display."""
        # Keep label formatting consistent across screens.
        return localization.translate_goal(goal, self._current_language())

    def _normalize_equipment_items(self, equipment: str) -> list[str]:
        """Normalize equipment tags into canonical display values."""
        # Delegate normalization to shared database helpers.
        return exercise_database.normalize_equipment_list(equipment)

    def _normalize_muscle_groups(self, muscle_group: str) -> list[str]:
        """Normalize muscle group tags into canonical display values."""
        # Delegate normalization to shared database helpers.
        return exercise_database.normalize_muscle_group_list(muscle_group)

    def _format_tag_display(self, items: Sequence[str]) -> str:
        """Join normalized tags for UI presentation."""
        # Use the shared formatting helper for consistent output.
        return exercise_database.format_tag_list(items)

    def _localize_muscle_label(self, value: str) -> str:
        """Translate canonical muscle group labels for display."""
        return localization.translate_muscle(value, self._current_language())

    def _localize_equipment_label(self, value: str) -> str:
        """Translate canonical equipment labels for display."""
        return localization.translate_equipment(value, self._current_language())

    def _localize_exercise_name(self, name: str) -> str:
        """Translate seeded exercise names when possible."""
        return localization.translate_exercise_name(name, self._current_language())

    def _localize_exercise_description(self, name: str, description: str) -> str:
        """Translate seeded exercise descriptions when possible."""
        return localization.translate_exercise_description(name, description, self._current_language())

    def _localize_exercise_instructions(self, name: str, instructions: str) -> str:
        """Translate seeded exercise instructions when possible."""
        return localization.translate_exercise_instructions(name, instructions, self._current_language())

    def _display_exercise_name(self, name: str) -> str:
        """Return the localized display name for a canonical exercise name."""
        return self._exercise_key_to_display.get(name, self._localize_exercise_name(name))

    def _resolve_exercise_name(self, name: str) -> str:
        """Map a displayed exercise name back to its canonical value."""
        return self._exercise_display_to_key.get(name, name)

    def _normalize_weight_unit(self, value: str) -> Optional[str]:
        """Normalize weight units to kg."""
        return exercise_database.normalize_weight_unit(value)

    def _format_weight_value(self, value: Optional[float]) -> str:
        """Format numeric weight values without trailing zeros."""
        if value is None:
            return ""
        try:
            return f"{float(value):g}"
        except (TypeError, ValueError):
            return ""

    def _format_weight_label(
        self,
        value: Optional[float],
        unit: Optional[str],
        *,
        supports_weight: bool = True,
    ) -> str:
        """Build a friendly weight label for UI display."""
        if not supports_weight:
            return self._t("Bodyweight")
        if value is None or not unit:
            return "—"
        formatted = self._format_weight_value(value)
        return f"{formatted} {unit}" if formatted else "—"

    def _adjust_weight_for_goal(self, value: Optional[float], goal: str) -> Optional[float]:
        """Adjust a base weight suggestion based on the selected goal."""
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        multiplier = self._goal_weight_multipliers.get(goal, 1.0)
        adjusted = numeric * multiplier
        if adjusted <= 0:
            return None
        return float(round(adjusted))

    def _record_for_name(self, name: str) -> Optional[dict[str, Any]]:
        """Return a record dict matching the given exercise name."""
        canonical = self._resolve_exercise_name(name)
        key = canonical.strip().lower()
        matches = [r for r in self.records if r.get("name", "").lower() == key]
        if not matches:
            return None
        goal_code = None
        if self.workout_goal_spinner_text and self.workout_goal_spinner_text != self._no_goal_label:
            goal_code = self._goal_label_map.get(self.workout_goal_spinner_text)
        if goal_code is None and self.user_profile_goal and self.user_profile_goal != self._no_goal_label:
            goal_code = self._goal_label_map.get(self.user_profile_goal)
        if goal_code:
            match = next((r for r in matches if r.get("goal") == goal_code), None)
            if match:
                return match
        goal_priority = {goal: idx for idx, goal in enumerate(exercise_database.GOALS)}
        return sorted(matches, key=lambda r: goal_priority.get(r.get("goal"), 99))[0]

    def _normalize_icon_key(self, value: str) -> str:
        """Build a lookup-friendly key from an icon name."""
        # Strip non-alphanumeric characters for fuzzy matching.
        return "".join(ch.lower() for ch in value if ch.isalnum())

    def _slugify_icon_name(self, value: str) -> str:
        """Generate a slug from a file name for spinner options."""
        # Convert separators into underscores and collapse repeats.
        cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
        return "_".join(part for part in cleaned.split("_") if part)

    def _build_icon_lookup(self) -> dict[str, str]:
        """Scan the Pictures folder and map icon keys to file paths."""
        # Load icon files once to avoid repeated disk scans.
        icon_dir = Path(__file__).with_name("Pictures")
        if not icon_dir.is_dir():
            return {}
        lookup: dict[str, str] = {}
        for entry in icon_dir.iterdir():
            if not entry.is_file():
                continue
            if entry.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                continue
            key = self._normalize_icon_key(entry.stem)
            if key and key not in lookup:
                lookup[key] = str(entry)
        return lookup

    def _build_icon_choice_options(self) -> list[str]:
        """Build the icon spinner options based on available images."""
        # Present a stable, sorted list with a fallback option.
        icon_dir = Path(__file__).with_name("Pictures")
        if not icon_dir.is_dir():
            return [self._no_icon_label]
        choices: list[str] = []
        for entry in sorted(icon_dir.iterdir(), key=lambda path: path.name.lower()):
            if not entry.is_file():
                continue
            if entry.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                continue
            slug = self._slugify_icon_name(entry.stem)
            if slug and slug not in choices:
                choices.append(slug)
        return [self._no_icon_label] + choices if choices else [self._no_icon_label]

    def _resolve_icon_source(self, icon_name: str) -> str:
        """Resolve an icon name to a file path using fuzzy matching."""
        # Attempt exact and pluralized lookups before prefix matching.
        if not icon_name:
            return ""
        key = self._normalize_icon_key(icon_name)
        if not key:
            return ""
        path = self._icon_lookup.get(key)
        if path:
            return path
        if not key.endswith("s"):
            path = self._icon_lookup.get(f"{key}s")
            if path:
                return path
        if key.endswith("s"):
            path = self._icon_lookup.get(key[:-1])
            if path:
                return path
        for candidate in sorted(self._icon_lookup):
            if candidate.startswith(key) or key.startswith(candidate):
                return self._icon_lookup[candidate]
        return ""

    def on_icon_choice_change(self, value: str) -> None:
        """Handle spinner selection for exercise icon choice."""
        # Normalize and resolve the icon source for preview.
        if not value or value in {self._no_icon_label, self._select_icon_label, self._no_icons_label}:
            self.icon_choice_spinner_text = self._no_icon_label
            self.add_icon_source = ""
            return
        self.icon_choice_spinner_text = value
        self.add_icon_source = self._resolve_icon_source(value)

    def _preferred_goal_label(self) -> str:
        """
        Pick a default goal label for forms:
        - Current recommendation goal if chosen
        - Else user's saved goal (if available)
        - Else "Muscle Building" (most common)
        - Else first available goal.
        """
        # Apply fallback order to find a meaningful default goal label.
        if self.rec_goal_spinner_text:
            return self.rec_goal_spinner_text
        if self.user_profile_goal and self.user_profile_goal in self.goal_choice_options:
            return self.user_profile_goal
        muscle_label = self._pretty_goal("muscle_building")
        if muscle_label in self.goal_choice_options:
            return muscle_label
        if self.goal_choice_options:
            return self.goal_choice_options[0]
        return ""

    def _default_workout_goal_label(self) -> str:
        """Select a default workout goal for the log form."""
        # Prefer a user profile goal when possible.
        if self.user_profile_goal and self.user_profile_goal in self.goal_choice_options:
            return self.user_profile_goal
        return self._no_goal_label

    def on_user_profile_goal(self, *_: Any) -> None:
        """Sync dependent goal state when the profile goal changes."""
        # Keep recommendation goal in sync with profile updates.
        self._sync_recommendation_goal()

    def _bootstrap_data(self, *_: Any) -> None:
        """Load initial records/users and prepare screen state."""
        # Run once after KV has created widgets.
        self.records = self._load_records()
        self.goal_choice_options = list(self._goal_label_map.keys())
        if not self.add_goal_spinner_text and self.goal_choice_options:
            self.add_goal_spinner_text = self._preferred_goal_label()
        self._update_filter_options()
        self.apply_filters()
        self._load_users()
        self._prefill_workout_date()
        # Start on the user screen so a user is chosen or created immediately.
        try:
            self.ids.screen_manager.current = "user"
        except Exception:
            pass
        if self.goal_choice_options and not self.rec_goal_spinner_text:
            self.rec_goal_spinner_text = self.goal_choice_options[0]

    def on_language_selected(self, label: str) -> None:
        """Switch the UI language based on spinner selection."""
        # Map display label back to language code.
        selected_code = None
        for code, name in localization.LANGUAGE_LABELS.items():
            if name == label:
                selected_code = code
                break
        if not selected_code:
            selected_code = localization.DEFAULT_LANGUAGE
        app = App.get_running_app()
        if app and getattr(app, "language", None) != selected_code:
            app.language = selected_code
        self.language_spinner_text = localization.LANGUAGE_LABELS.get(selected_code, label)
        if getattr(self, "_initializing", False):
            return
        self.apply_language()

    def apply_language(self) -> None:
        """Refresh translated labels and lists after a language change."""
        # Preserve selections using canonical keys before rebuilding labels.
        old_goal_map = dict(self._goal_label_map)
        old_muscle_map = dict(self._muscle_display_to_key)
        old_equipment_map = dict(self._equipment_display_to_key)
        old_exercise_map = dict(self._exercise_display_to_key)
        old_no_icon = getattr(self, "_no_icon_label", "No icon")
        old_select_icon = getattr(self, "_select_icon_label", "Select icon")
        old_no_icons = getattr(self, "_no_icons_label", "No icons found")
        old_select_exercise = getattr(self, "_select_exercise_label", "Select exercise")
        old_no_matches = getattr(self, "_no_matches_label", "No matches")
        old_no_exercises = getattr(self, "_no_exercises_label", "No exercises")

        add_goal_code = old_goal_map.get(self.add_goal_spinner_text)
        register_goal_code = old_goal_map.get(self.register_goal_spinner_text)
        profile_goal_code = old_goal_map.get(self.user_profile_goal)
        rec_goal_code = old_goal_map.get(self.rec_goal_spinner_text)
        workout_goal_code = localization.goal_code_from_label(self.workout_goal_spinner_text)

        add_muscle_key = old_muscle_map.get(self.add_muscle_spinner_text)
        add_equipment_key = old_equipment_map.get(self.add_equipment_spinner_text)

        history_exercise_key = old_exercise_map.get(self.history_exercise_spinner_text)
        icon_choice = self.icon_choice_spinner_text
        icon_is_placeholder = icon_choice in {old_no_icon, old_select_icon, old_no_icons}

        self._apply_language_defaults()
        self._rebuild_goal_maps()
        self.records = self._load_records()
        self._update_filter_options()

        if self.rec_recommendations:
            for rec in self.rec_recommendations:
                record = next((r for r in self.records if r["name"] == rec.get("name")), None)
                if record:
                    rec["display_name"] = record.get("display_name", rec.get("name", ""))
                    rec["description"] = record.get("description", rec.get("description", ""))
                    rec["execution_instructions"] = record.get(
                        "execution_instructions", rec.get("execution_instructions", "")
                    )
                    rec["muscle_group"] = record.get("muscle_group", rec.get("muscle_group", ""))
                    rec["equipment"] = record.get("equipment", rec.get("equipment", ""))
                    rec["recommendation"] = record.get("recommendation", rec.get("recommendation", ""))
                    rec["goal_label"] = record.get("goal_label", rec.get("goal_label", ""))
            self._recommend_screen().ids.rec_list.data = self.rec_recommendations

        if self.rec_plan:
            for item in self.rec_plan:
                record = next((r for r in self.records if r["name"] == item.get("name")), None)
                if record:
                    item["display_name"] = record.get("display_name", item.get("name", ""))
                    item["execution_instructions"] = record.get(
                        "execution_instructions", item.get("execution_instructions", "")
                    )
                    item["muscle_group"] = record.get("muscle_group", item.get("muscle_group", ""))
                    item["equipment"] = record.get("equipment", item.get("equipment", ""))
                    item["recommendation"] = record.get("recommendation", item.get("recommendation", ""))
                item["display"] = self._t(
                    "{name} ({minutes} min)",
                    name=item.get("display_name", item.get("name", "")),
                    minutes=item.get("estimated_minutes", "0"),
                )
            self._refresh_recommendation_view()

        if self.live_exercises:
            for ex in self.live_exercises:
                record = next((r for r in self.records if r["name"] == ex.get("name")), None)
                if record:
                    ex["display_name"] = record.get("display_name", ex.get("name", ""))
                    ex["description"] = record.get("description", ex.get("description", ""))
                    ex["execution_instructions"] = record.get(
                        "execution_instructions", ex.get("execution_instructions", "")
                    )
                    ex["muscle_group"] = record.get("muscle_group", ex.get("muscle_group", ""))
                    ex["equipment"] = record.get("equipment", ex.get("equipment", ""))
                    ex["recommendation"] = record.get("recommendation", ex.get("recommendation", ""))

        if self.filter_goal != ALL_FILTER:
            self.goal_spinner_text = self._goal_code_label_map.get(self.filter_goal, self._all_goals_label)
        else:
            self.goal_spinner_text = self._all_goals_label
        if self.filter_muscle_group != ALL_FILTER:
            self.muscle_spinner_text = self._muscle_key_to_display.get(
                self.filter_muscle_group, self._all_muscle_groups_label
            )
        else:
            self.muscle_spinner_text = self._all_muscle_groups_label
        if self.filter_equipment != ALL_FILTER:
            self.equipment_spinner_text = self._equipment_key_to_display.get(
                self.filter_equipment, self._all_equipment_label
            )
        else:
            self.equipment_spinner_text = self._all_equipment_label

        if add_goal_code:
            self.add_goal_spinner_text = self._goal_code_label_map.get(add_goal_code, self._preferred_goal_label())
        elif self.goal_choice_options:
            self.add_goal_spinner_text = self._preferred_goal_label()

        if register_goal_code:
            self.register_goal_spinner_text = self._goal_code_label_map.get(register_goal_code, self._no_goal_label)
        else:
            self.register_goal_spinner_text = self._no_goal_label

        if profile_goal_code:
            self.user_profile_goal = self._goal_code_label_map.get(profile_goal_code, self._no_goal_label)
        else:
            self.user_profile_goal = self._no_goal_label

        if rec_goal_code:
            self.rec_goal_spinner_text = self._goal_code_label_map.get(rec_goal_code, "")
        elif self.goal_choice_options:
            self.rec_goal_spinner_text = self.goal_choice_options[0]

        if workout_goal_code:
            self.workout_goal_spinner_text = self._goal_code_label_map.get(workout_goal_code, self._no_goal_label)
        else:
            self.workout_goal_spinner_text = self._no_goal_label

        if add_muscle_key:
            self.add_muscle_spinner_text = self._muscle_key_to_display.get(add_muscle_key, "")
        elif self.muscle_choice_options:
            self.add_muscle_spinner_text = self.muscle_choice_options[0]

        if add_equipment_key:
            self.add_equipment_spinner_text = self._equipment_key_to_display.get(add_equipment_key, "")
        elif self.equipment_choice_options:
            self.add_equipment_spinner_text = self.equipment_choice_options[0]

        if icon_is_placeholder:
            self.icon_choice_spinner_text = self._no_icon_label
        elif self.icon_choice_spinner_text not in self.icon_choice_options:
            self.icon_choice_spinner_text = self._no_icon_label

        if history_exercise_key:
            self.history_exercise_spinner_text = self._exercise_key_to_display.get(
                history_exercise_key, self._select_exercise_label
            )
        elif self.history_exercise_spinner_text in {old_select_exercise, old_no_matches, old_no_exercises}:
            self.history_exercise_spinner_text = self._select_exercise_label

        self.add_supports_weight_spinner_text = self._t("Yes") if self.add_supports_weight else self._t("No")
        self._update_filter_colors()
        self.apply_filters()
        self._load_history()
        self._update_live_labels()

    def _load_records(self) -> list[dict[str, Any]]:
        """Fetch exercise rows and normalize them for UI usage."""
        # Convert database rows into dictionaries used by filters and lists.
        with exercise_database.get_connection() as conn:
            rows = exercise_database.fetch_all(conn)
        records: list[dict[str, Any]] = []
        self._exercise_display_to_key = {}
        self._exercise_key_to_display = {}
        for (
            name,
            icon,
            description,
            execution_instructions,
            equipment,
            muscle_group,
            supports_weight,
            default_weight_value,
            default_weight_unit,
            goal,
            rating,
            sets,
            reps,
            time_seconds,
        ) in rows:
            if not name or not description:
                continue
            canonical_name = name
            display_name = self._localize_exercise_name(canonical_name)
            display_description = self._localize_exercise_description(canonical_name, description)
            display_instructions = self._localize_exercise_instructions(
                canonical_name, execution_instructions or ""
            )
            muscle_items = self._normalize_muscle_groups(muscle_group)
            equipment_items = self._normalize_equipment_items(equipment)
            muscle_display_items = [self._localize_muscle_label(item) for item in muscle_items]
            equipment_display_items = [self._localize_equipment_label(item) for item in equipment_items]
            muscle_display = self._format_tag_display(muscle_display_items) or muscle_group
            equipment_display = self._format_tag_display(equipment_display_items) or equipment
            recommendation_parts = []
            if sets is not None and reps is not None:
                recommendation_parts.append(
                    self._t("{sets} sets x {reps} reps", sets=sets, reps=reps)
                )
            elif sets is not None:
                recommendation_parts.append(self._t("{sets} sets", sets=sets))
            if time_seconds is not None:
                recommendation_parts.append(
                    self._t("{seconds}s hold", seconds=time_seconds)
                )
            icon_value = icon or ""
            icon_source = self._resolve_icon_source(icon_value)
            if not icon_source and canonical_name:
                icon_source = self._resolve_icon_source(canonical_name)
            supports_weight_flag = bool(supports_weight)
            if supports_weight is None:
                supports_weight_flag = exercise_database.infer_supports_weight(equipment_display)
            normalized_weight_unit = exercise_database.normalize_weight_unit(default_weight_unit)
            if supports_weight_flag and not normalized_weight_unit:
                normalized_weight_unit = "kg"
            adjusted_weight_value = None
            if supports_weight_flag and default_weight_value is not None:
                adjusted_weight_value = self._adjust_weight_for_goal(default_weight_value, goal)
            if not supports_weight_flag:
                normalized_weight_unit = None
                adjusted_weight_value = None
            if supports_weight_flag and adjusted_weight_value is not None:
                weight_label = self._format_weight_value(adjusted_weight_value)
                if weight_label and normalized_weight_unit:
                    recommendation_parts.append(
                        self._t(
                            "Weight {value} {unit}",
                            value=weight_label,
                            unit=normalized_weight_unit,
                        )
                    )
            recommendation = " • ".join(recommendation_parts) if recommendation_parts else self._t(
                "Adjust volume to preference"
            )
            self._exercise_key_to_display.setdefault(canonical_name, display_name)
            self._exercise_display_to_key.setdefault(display_name, canonical_name)
            records.append(
                {
                    "name": canonical_name,
                    "display_name": display_name,
                    "icon": icon_value,
                    "icon_source": icon_source,
                    "description": display_description,
                    "execution_instructions": display_instructions,
                    "equipment": equipment_display,
                    "equipment_items": set(equipment_items),
                    "muscle_group": muscle_display,
                    "muscle_groups": set(muscle_items),
                    "supports_weight": supports_weight_flag,
                    "default_weight_value": adjusted_weight_value,
                    "default_weight_unit": normalized_weight_unit,
                    "goal": goal,
                    "goal_label": self._pretty_goal(goal),
                    "suitability_display": f"{rating}/10",
                    "rating": rating,
                    "sets": sets,
                    "reps": reps,
                    "time_seconds": time_seconds,
                    "recommendation": recommendation,
                }
            )
        return records

    def _update_filter_options(self) -> None:
        """Refresh filter option lists and spinner defaults."""
        # Regenerate filter choices based on available records.
        selected_muscle_key = self._muscle_display_to_key.get(self.add_muscle_spinner_text)
        selected_equipment_key = self._equipment_display_to_key.get(self.add_equipment_spinner_text)
        muscle_keys = sorted(
            {item for record in self.records for item in record.get("muscle_groups", set())}
        )
        equipment_keys = sorted(
            {item for record in self.records for item in record.get("equipment_items", set())}
        )
        if "Dumbbell" not in equipment_keys:
            equipment_keys.append("Dumbbell")

        self._muscle_key_to_display = {
            key: self._localize_muscle_label(key) for key in muscle_keys
        }
        self._muscle_display_to_key = {value: key for key, value in self._muscle_key_to_display.items()}
        muscle_choices = [self._muscle_key_to_display[key] for key in muscle_keys]
        self.muscle_choice_options = muscle_choices
        self.muscle_choice_display = ", ".join(muscle_choices) if muscle_choices else self._t("No known groups yet.")
        if selected_muscle_key:
            self.add_muscle_spinner_text = self._muscle_key_to_display.get(selected_muscle_key, "")
        if not self.add_muscle_spinner_text and muscle_choices:
            self.add_muscle_spinner_text = muscle_choices[0]
        if muscle_choices and self.add_muscle_spinner_text not in muscle_choices:
            self.add_muscle_spinner_text = muscle_choices[0]

        self._equipment_key_to_display = {
            key: self._localize_equipment_label(key) for key in equipment_keys
        }
        self._equipment_display_to_key = {
            value: key for key, value in self._equipment_key_to_display.items()
        }
        equipment_choices = [self._equipment_key_to_display[key] for key in equipment_keys]
        if not equipment_choices:
            equipment_choices = [self._t("Bodyweight")]
            self._equipment_key_to_display = {"Bodyweight": equipment_choices[0]}
            self._equipment_display_to_key = {equipment_choices[0]: "Bodyweight"}
        self.equipment_choice_options = equipment_choices
        self.equipment_choice_display = ", ".join(self.equipment_choice_options) if self.equipment_choice_options else ""
        if selected_equipment_key:
            self.add_equipment_spinner_text = self._equipment_key_to_display.get(selected_equipment_key, "")
        if not self.add_equipment_spinner_text and equipment_choices:
            self.add_equipment_spinner_text = equipment_choices[0]
        self.on_add_equipment_change(self._resolve_equipment_choice(self.add_equipment_spinner_text))

        self.goal_options = [self._all_goals_label] + self.goal_choice_options
        self.user_goal_options = [self._no_goal_label] + self.goal_choice_options
        muscle_options = [self._all_muscle_groups_label] + muscle_choices
        equipment_options = [self._all_equipment_label] + equipment_choices
        if self.muscle_spinner_text not in muscle_options:
            self.muscle_spinner_text = self._all_muscle_groups_label
            self.filter_muscle_group = ALL_FILTER
        if self.equipment_spinner_text not in equipment_options:
            self.equipment_spinner_text = self._all_equipment_label
            self.filter_equipment = ALL_FILTER
        self.muscle_options = muscle_options
        self.equipment_options = equipment_options
        if self.goal_choice_options and self.add_goal_spinner_text not in self.goal_choice_options:
            self.add_goal_spinner_text = self._preferred_goal_label()
        if self.user_profile_goal not in self.user_goal_options:
            self.user_profile_goal = self._no_goal_label
        self.history_exercise_options = sorted(
            {r.get("display_name", r.get("name", "")) for r in self.records if r.get("name")}
        )
        self._refresh_history_exercise_filtered_options()
        self.workout_goal_options = [self._no_goal_label] + self.goal_choice_options
        if self.workout_goal_spinner_text not in self.workout_goal_options:
            self.workout_goal_spinner_text = self._no_goal_label
        if self.register_goal_spinner_text not in self.user_goal_options:
            self.register_goal_spinner_text = self._no_goal_label
        self._sync_recommendation_goal()
        self._update_filter_colors()

    def _resolve_filter_colors(
        self,
        value: str,
        default_value: str,
        active_color: tuple[float, float, float, float],
        inactive_color: tuple[float, float, float, float],
        inactive_text: tuple[float, float, float, float],
        active_text: tuple[float, float, float, float],
    ) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
        """Return color/text tuples based on whether a filter is active."""
        # Use active colors when the selection differs from default.
        if value and value != default_value:
            return active_color, active_text
        return inactive_color, inactive_text

    def _update_filter_colors(self) -> None:
        """Update spinner colors to reflect active filters."""
        # Apply a shared color theme across filter controls.
        inactive_color = (0.93, 0.95, 0.98, 1)
        inactive_text = (0.2, 0.2, 0.25, 1)
        active_text = (1, 1, 1, 1)
        self.filter_goal_color, self.filter_goal_text_color = self._resolve_filter_colors(
            self.goal_spinner_text,
            self._all_goals_label,
            (0.18, 0.5, 0.85, 1),
            inactive_color,
            inactive_text,
            active_text,
        )
        self.filter_muscle_color, self.filter_muscle_text_color = self._resolve_filter_colors(
            self.muscle_spinner_text,
            self._all_muscle_groups_label,
            (0.2, 0.65, 0.38, 1),
            inactive_color,
            inactive_text,
            active_text,
        )
        self.filter_equipment_color, self.filter_equipment_text_color = self._resolve_filter_colors(
            self.equipment_spinner_text,
            self._all_equipment_label,
            (0.9, 0.55, 0.2, 1),
            inactive_color,
            inactive_text,
            active_text,
        )

    def _normalize_filter_selection(self, selection: Any) -> set[str]:
        """Normalize filter values into a comparable set."""
        # Treat "All" and empty values as no filter.
        if not selection or selection == ALL_FILTER:
            return set()
        if isinstance(selection, (list, tuple, set)):
            return {item for item in selection if item and item != ALL_FILTER}
        return {str(selection)}

    def _record_matches_tag_filters(self, record: dict[str, Any]) -> bool:
        """Check whether a record matches selected muscle/equipment filters."""
        # Compare record tags against the selected filter values.
        selected_muscles = self._normalize_filter_selection(self.filter_muscle_group)
        if selected_muscles:
            record_muscles = set(record.get("muscle_groups") or [])
            if not selected_muscles.intersection(record_muscles):
                return False
        selected_equipment = self._normalize_filter_selection(self.filter_equipment)
        if selected_equipment:
            record_equipment = set(record.get("equipment_items") or [])
            if not selected_equipment.intersection(record_equipment):
                return False
        return True

    def _sync_recommendation_goal(self) -> None:
        """Align recommendation goal with the user profile when possible."""
        # Use the profile goal unless the UI already has a valid selection.
        if self.user_profile_goal and self.user_profile_goal in self.goal_choice_options:
            self.rec_goal_spinner_text = self.user_profile_goal
        elif self.goal_choice_options and self.rec_goal_spinner_text not in self.goal_choice_options:
            self.rec_goal_spinner_text = self.goal_choice_options[0]

    def on_rec_plan(self, *_: Any) -> None:
        """Recalculate UI layout when the plan changes."""
        # Keep plan list height in sync with item count.
        self._update_rec_plan_height()

    def _compute_rec_plan_height(self) -> float:
        """Calculate plan list height within min/max limits."""
        # Cap the height so the list remains scrollable.
        min_height = dp(70)
        max_height = dp(240)
        item_height = dp(92)
        spacing = dp(6)
        count = len(self.rec_plan)
        if count <= 0:
            return min_height
        total = count * item_height + max(0, count - 1) * spacing
        return min(max_height, max(min_height, total))

    def _update_rec_plan_height(self) -> None:
        """Update the bound height property for the plan list."""
        # Trigger KV layout updates when the plan size changes.
        self.rec_plan_height = self._compute_rec_plan_height()

    def _refresh_history_exercise_filtered_options(self) -> None:
        """Filter history exercise dropdown based on search input."""
        # Keep the spinner options aligned with the text filter.
        query = self.history_exercise_filter.strip().lower()
        if query:
            filtered = [name for name in self.history_exercise_options if query in name.lower()]
        else:
            filtered = list(self.history_exercise_options)
        self.history_exercise_filtered_options = filtered
        if filtered:
            if self.history_exercise_spinner_text not in filtered:
                self.history_exercise_spinner_text = self._select_exercise_label
        else:
            self.history_exercise_spinner_text = (
                self._no_matches_label if self.history_exercise_options else self._no_exercises_label
            )

    def filter_history_exercise_options(self, query: str) -> None:
        """Apply the history exercise filter to the dropdown."""
        # Persist the filter string and recompute the options list.
        self.history_exercise_filter = query
        self._refresh_history_exercise_filtered_options()

    def clear_history_exercise_filter(self) -> None:
        """Clear the history exercise search filter."""
        # Reset both the text input and the filtered list.
        ids = self._workout_form_ids()
        if ids and "history_exercise_filter_input" in ids:
            ids.history_exercise_filter_input.text = ""
        else:
            self.history_exercise_filter = ""
            self._refresh_history_exercise_filtered_options()

    def _resolve_equipment_choice(self, current: str) -> str:
        """Return a valid equipment choice, preferring Bodyweight."""
        # Ensure the add form always has a valid equipment selection.
        if current and current in self.equipment_choice_options:
            return current
        bodyweight_label = self._localize_equipment_label("Bodyweight")
        if bodyweight_label in self.equipment_choice_options:
            return bodyweight_label
        if self.equipment_choice_options:
            return self.equipment_choice_options[0]
        return bodyweight_label

    def set_add_supports_weight(self, value: str) -> None:
        """Update the add-exercise weight support selection."""
        # Keep the spinner text and boolean flag aligned.
        normalized = (value or "").strip().lower()
        yes_label = self._t("Yes").strip().lower()
        supports = normalized in {yes_label, "yes", "ja", "true", "1"}
        self.add_supports_weight = supports
        self.add_supports_weight_spinner_text = self._t("Yes") if supports else self._t("No")
        if supports and not self.add_weight_unit_spinner_text:
            self.add_weight_unit_spinner_text = "kg"

    def on_add_equipment_change(self, value: str) -> None:
        """Update equipment selection and infer weight support."""
        # Auto-suggest weight support based on equipment choice.
        self.add_equipment_spinner_text = value
        equipment_key = self._equipment_display_to_key.get(value, value)
        supports = exercise_database.infer_supports_weight(equipment_key)
        self.add_supports_weight = supports
        self.add_supports_weight_spinner_text = self._t("Yes") if supports else self._t("No")
        if supports and not self.add_weight_unit_spinner_text:
            self.add_weight_unit_spinner_text = "kg"

    def _browse_screen(self) -> BrowseScreen:
        """Return the browse screen instance."""
        # Centralize screen access to avoid repeated lookups.
        return self.ids.screen_manager.get_screen("browse")

    def _add_screen(self) -> AddScreen:
        """Return the add screen instance."""
        # Centralize screen access to avoid repeated lookups.
        return self.ids.screen_manager.get_screen("add")

    def _user_screen(self) -> UserScreen:
        """Return the user screen instance."""
        # Centralize screen access to avoid repeated lookups.
        return self.ids.screen_manager.get_screen("user")

    def _register_screen(self) -> RegisterScreen:
        """Return the register screen instance."""
        # Centralize screen access to avoid repeated lookups.
        return self.ids.screen_manager.get_screen("register")

    def _history_screen(self) -> HistoryScreen:
        """Return the history screen instance."""
        # Centralize screen access to avoid repeated lookups.
        return self.ids.screen_manager.get_screen("history")

    def _recommend_screen(self) -> RecommendationScreen:
        """Return the recommendation screen instance."""
        # Centralize screen access to avoid repeated lookups.
        return self.ids.screen_manager.get_screen("recommend")

    def _workout_form_ids(self) -> Optional[Any]:
        """Return the ids dict for the workout log modal."""
        # Gate access when the modal is not open.
        if self._workout_log_modal is not None:
            return self._workout_log_modal.ids
        return None

    def _prefill_workout_date(self) -> None:
        """Populate the workout date field with today's date if available."""
        # Only set defaults when the field is empty.
        ids = self._workout_form_ids()
        if not ids:
            return
        date_field = ids.get("workout_date_input")
        if date_field and not date_field.text:
            date_field.text = date.today().isoformat()

    def _flash_color(
        self,
        base: tuple[float, float, float, float],
        text: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float]:
        """Compute a contrast-aware highlight color."""
        # Adjust luminance to keep the flash readable.
        luma = 0.2126 * text[0] + 0.7152 * text[1] + 0.0722 * text[2]
        factor = 0.18
        if luma > 0.6:
            return (
                max(0.0, base[0] * (1 - factor)),
                max(0.0, base[1] * (1 - factor)),
                max(0.0, base[2] * (1 - factor)),
                base[3],
            )
        return (
            min(1.0, base[0] + (1 - base[0]) * factor),
            min(1.0, base[1] + (1 - base[1]) * factor),
            min(1.0, base[2] + (1 - base[2]) * factor),
            base[3],
        )

    def _animate_input_feedback(self, widget: Any) -> None:
        """Briefly flash inputs to indicate value acceptance."""
        # Use Kivy animations when a widget supports background_color.
        if not widget or not hasattr(widget, "background_color"):
            return
        try:
            Animation.cancel_all(widget, "background_color")
        except Exception:
            pass
        base_color = tuple(getattr(widget, "background_color", (1, 1, 1, 1)))
        text_color = tuple(getattr(widget, "color", (0, 0, 0, 1)))
        flash_color = self._flash_color(base_color, text_color)
        (Animation(background_color=flash_color, duration=0.08, t="out_quad")
         + Animation(background_color=base_color, duration=0.25, t="out_quad")).start(widget)

    def confirm_value_input(self, widget: Any) -> None:
        """Track value changes and provide confirmation feedback."""
        # Avoid feedback loops by storing the last confirmed value.
        if not widget or not hasattr(widget, "text"):
            return
        current = getattr(widget, "text", "")
        if not getattr(widget, "get_root_window", None) or not widget.get_root_window():
            setattr(widget, "_last_confirmed_value", current)
            return
        last_value = getattr(widget, "_last_confirmed_value", None)
        if last_value is None and hasattr(widget, "values"):
            setattr(widget, "_last_confirmed_value", current)
            return
        if last_value is None and current == "":
            setattr(widget, "_last_confirmed_value", current)
            return
        if last_value == current:
            return
        setattr(widget, "_last_confirmed_value", current)
        Clock.schedule_once(lambda *_: self._animate_input_feedback(widget), 0)

    def on_goal_change(self, value: str) -> None:
        """Handle selection changes for the goal filter."""
        # Update filter state and refresh the browse list.
        if value == self._all_goals_label:
            self.filter_goal = ALL_FILTER
        else:
            self.filter_goal = self._goal_label_map.get(value, ALL_FILTER)
        self.goal_spinner_text = value
        self._update_filter_colors()
        self.apply_filters()

    def on_muscle_change(self, value: str) -> None:
        """Handle selection changes for the muscle filter."""
        # Update filter state and refresh the browse list.
        if value == self._all_muscle_groups_label:
            self.filter_muscle_group = ALL_FILTER
        else:
            self.filter_muscle_group = self._muscle_display_to_key.get(value, value)
        self.muscle_spinner_text = value
        self._update_filter_colors()
        self.apply_filters()

    def on_equipment_change(self, value: str) -> None:
        """Handle selection changes for the equipment filter."""
        # Update filter state and refresh the browse list.
        if value == self._all_equipment_label:
            self.filter_equipment = ALL_FILTER
        else:
            self.filter_equipment = self._equipment_display_to_key.get(value, value)
        self.equipment_spinner_text = value
        self._update_filter_colors()
        self.apply_filters()

    def apply_filters(self) -> None:
        """Apply current filters and refresh the browse list."""
        # Build the filtered list with goal-aware grouping.
        filtered: list[dict[str, str]] = []
        goal_priority = {goal: idx for idx, goal in enumerate(exercise_database.GOALS)}
        recency_map = self._recency_days_map()
        if self.filter_goal == ALL_FILTER:
            grouped: dict[str, dict[str, Any]] = {}
            for record in self.records:
                if not record.get("name") or not record.get("description"):
                    continue
                if not self._record_matches_tag_filters(record):
                    continue
                existing = grouped.get(record["name"])
                if not existing:
                    grouped[record["name"]] = record
                    continue
                if record["rating"] > existing["rating"]:
                    grouped[record["name"]] = record
                elif record["rating"] == existing["rating"]:
                    if goal_priority.get(record["goal"], 0) < goal_priority.get(existing["goal"], 0):
                        grouped[record["name"]] = record
            for record in sorted(grouped.values(), key=lambda r: r.get("display_name") or r["name"]):
                suitability_display = f'{record["goal_label"]} ({record["suitability_display"]})'
                suitability_value = record.get("suitability_display", "")
                est_minutes = self._estimate_minutes(record)
                recency_days = recency_map.get(record["name"])
                score = self._score_recommendation(record, recency_days)
                sets = record.get("sets")
                reps = record.get("reps")
                time_seconds = record.get("time_seconds")
                sets_display = str(sets) if sets is not None else "—"
                reps_display = str(reps) if reps is not None else "—"
                if time_seconds is None:
                    time_display = "—"
                else:
                    time_display = self._t("{seconds} sec", seconds=time_seconds)
                filtered.append(
                    {
                        "name": record["name"],
                        "display_name": record.get("display_name", record["name"]),
                        "icon_source": record.get("icon_source", ""),
                        "description": record["description"],
                        "execution_instructions": record.get("execution_instructions", ""),
                        "goal_label": record["goal_label"],
                        "muscle_group": record["muscle_group"],
                        "equipment": record["equipment"],
                        "suitability_display": suitability_display,
                        "suitability_value": suitability_value,
                        "estimated_minutes": str(est_minutes),
                        "score_display": str(score),
                        "recommendation": record["recommendation"],
                        "sets_display": sets_display,
                        "reps_display": reps_display,
                        "time_display": time_display,
                    }
                )
        else:
            for record in self.records:
                if not record.get("name") or not record.get("description"):
                    continue
                if record["goal"] != self.filter_goal:
                    continue
                if not self._record_matches_tag_filters(record):
                    continue
                suitability_display = record["suitability_display"]
                suitability_value = record.get("suitability_display", "")
                est_minutes = self._estimate_minutes(record)
                recency_days = recency_map.get(record["name"])
                score = self._score_recommendation(record, recency_days)
                sets = record.get("sets")
                reps = record.get("reps")
                time_seconds = record.get("time_seconds")
                sets_display = str(sets) if sets is not None else "—"
                reps_display = str(reps) if reps is not None else "—"
                if time_seconds is None:
                    time_display = "—"
                else:
                    time_display = self._t("{seconds} sec", seconds=time_seconds)
                filtered.append(
                    {
                        "name": record["name"],
                        "display_name": record.get("display_name", record["name"]),
                        "icon_source": record.get("icon_source", ""),
                        "description": record["description"],
                        "execution_instructions": record.get("execution_instructions", ""),
                        "goal_label": record["goal_label"],
                        "muscle_group": record["muscle_group"],
                        "equipment": record["equipment"],
                        "suitability_display": suitability_display,
                        "suitability_value": suitability_value,
                        "estimated_minutes": str(est_minutes),
                        "score_display": str(score),
                        "recommendation": record["recommendation"],
                        "sets_display": sets_display,
                        "reps_display": reps_display,
                        "time_display": time_display,
                    }
                )
        exercise_list = self._browse_screen().ids.exercise_list
        # Clear first to avoid stale/blank items from previous data set.
        exercise_list.data = []
        exercise_list.refresh_from_data()
        exercise_list.data = filtered
        exercise_list.refresh_from_data()
        self.browse_empty = not filtered

    def _load_users(self) -> None:
        """Load users from the database and refresh UI state."""
        # Keep current user selection consistent across reloads.
        with exercise_database.get_connection() as conn:
            rows = exercise_database.fetch_users(conn)
        self._users = [
            {
                "id": user_id,
                "username": username,
                "display_name": display_name or username,
                "preferred_goal": preferred_goal,
            }
            for user_id, username, display_name, preferred_goal in rows
        ]
        self.user_options = [u["username"] for u in self._users]

        if self.current_user_id and not any(u["id"] == self.current_user_id for u in self._users):
            self.current_user_id = None

        if not self.current_user_id:
            example_user = next(
                (u for u in self._users if u["username"] == exercise_database.EXAMPLE_USERNAME),
                None,
            )
            if example_user:
                self.current_user_id = example_user["id"]

        if self.current_user_id:
            current = next((u for u in self._users if u["id"] == self.current_user_id), None)
            if current:
                self.current_user_display = current["display_name"]
                self.user_spinner_text = current["username"]
                self.user_profile_name = current["display_name"]
                preferred_goal = current.get("preferred_goal")
                if preferred_goal:
                    goal_code = localization.goal_code_from_label(preferred_goal) or preferred_goal
                    self.user_profile_goal = self._goal_code_label_map.get(goal_code, self._no_goal_label)
                else:
                    self.user_profile_goal = self._no_goal_label
        if not self.current_user_id:
            self.current_user_display = self._no_user_label
            self.user_spinner_text = self._select_user_label
            self.user_profile_name = ""
            self.user_profile_goal = self._no_goal_label

        self._load_history()

    def _set_user_status(self, message: str, *, error: bool = False) -> None:
        """Update status banner on the user screen."""
        # Use red for errors and green for success messages.
        self.user_status_text = message
        self.user_status_color = (0.65, 0.16, 0.16, 1) if error else (0.14, 0.4, 0.2, 1)

    def _set_register_status(self, message: str, *, error: bool = False) -> None:
        """Update status banner on the registration screen."""
        # Use red for errors and green for success messages.
        self.register_status_text = message
        self.register_status_color = (0.65, 0.16, 0.16, 1) if error else (0.14, 0.4, 0.2, 1)

    def _set_user_profile_status(self, message: str, *, error: bool = False) -> None:
        """Update status banner on the profile section."""
        # Use red for errors and green for success messages.
        self.user_profile_status_text = message
        self.user_profile_status_color = (0.65, 0.16, 0.16, 1) if error else (0.14, 0.4, 0.2, 1)

    def _require_user(self) -> bool:
        """Ensure a user is selected before continuing."""
        # Redirect to the user screen when missing.
        if not self.current_user_id:
            self._set_user_status(self._t("Select or create a user to continue."), error=True)
            try:
                self.ids.screen_manager.current = "user"
            except Exception:
                pass
            return False
        return True

    def handle_register_user(self) -> None:
        """Create a new user account from the register form."""
        # Validate inputs before inserting into the database.
        try:
            ids = self._register_screen().ids
        except Exception:
            self._set_register_status(self._t("Registration screen not available."), error=True)
            return
        username = ids.register_username_input.text.strip()
        if not username:
            self._set_register_status(self._t("Username is required."), error=True)
            return
        display_name = ids.register_display_input.text.strip() or None
        goal_label = ids.register_goal_spinner.text.strip()
        preferred_goal = None
        if goal_label and goal_label != self._no_goal_label:
            preferred_goal = self._goal_label_map.get(goal_label)
            if not preferred_goal:
                self._set_register_status(self._t("Select a valid goal option."), error=True)
                return

        try:
            new_user_id = exercise_database.add_user(
                username=username,
                display_name=display_name,
                preferred_goal=preferred_goal,
            )
        except ValueError as exc:
            self._set_register_status(self._t(str(exc)), error=True)
            return
        except sqlite3.IntegrityError:
            self._set_register_status(self._t("Username already exists. Choose another."), error=True)
            return
        except sqlite3.DatabaseError as exc:
            self._set_register_status(self._t("Database error: {error}", error=exc), error=True)
            return

        ids.register_username_input.text = ""
        ids.register_display_input.text = ""
        self.register_goal_spinner_text = self._no_goal_label
        self.current_user_id = new_user_id
        self._load_users()
        self._set_user_status(self._t("User '{username}' registered.", username=username))
        self._set_register_status(self._t("User '{username}' registered.", username=username))
        self.go_home()

    def prompt_delete_user(self) -> None:
        """Open the delete user selection modal."""
        # Require at least one user before opening the modal.
        if not self._users:
            self._set_user_status(self._t("Select a user to delete."), error=True)
            return
        if self._delete_user_modal is not None:
            try:
                self._delete_user_modal.dismiss()
            except Exception:
                pass
        self._reset_delete_user_selection()
        modal = DeleteUserModal()
        modal.bind(on_dismiss=self._clear_delete_user_modal)
        self._delete_user_modal = modal
        modal.open()

    def dismiss_delete_user_modal(self) -> None:
        """Dismiss the delete user modal and reset selection."""
        self._reset_delete_user_selection()

    def _clear_delete_user_modal(self, *_: Any) -> None:
        """Clear the cached delete user modal reference."""
        self._delete_user_modal = None

    def _reset_delete_user_selection(self) -> None:
        """Reset delete user selection state."""
        self.delete_user_spinner_text = self._select_user_label
        self.delete_user_ready = False
        self._pending_delete_user_id = None
        self._pending_delete_username = ""

    def on_delete_user_selected(self, username: str) -> None:
        """Capture the user selection for deletion."""
        self.delete_user_spinner_text = username
        selected = next((u for u in self._users if u["username"] == username), None)
        if not selected:
            self.delete_user_ready = False
            self._pending_delete_user_id = None
            self._pending_delete_username = ""
            return
        self._pending_delete_user_id = selected["id"]
        self._pending_delete_username = selected["username"]
        self.delete_user_ready = True

    def confirm_delete_user_selection(self) -> None:
        """Confirm deletion of the chosen user."""
        user_id = self._pending_delete_user_id
        username = self._pending_delete_username
        if user_id is None:
            self._set_user_status(self._t("Select a user to delete."), error=True)
            return
        message = self._t(
            "Delete user '{username}'? This will remove all workout history.",
            username=username,
        )
        self._open_confirm_action(
            message,
            self._t("Delete user"),
            lambda user_id=user_id, username=username: self._delete_user_by_id(user_id, username),
        )
        self._reset_delete_user_selection()

    def _delete_user_by_id(self, user_id: int, username: str) -> None:
        """Delete the selected user and their associated data."""
        try:
            deleted = exercise_database.delete_user(user_id=user_id)
        except sqlite3.DatabaseError as exc:
            self._set_user_status(self._t("Database error: {error}", error=exc), error=True)
            return
        if not deleted:
            self._set_user_status(self._t("User not found."), error=True)
            return
        if self.current_user_id == user_id:
            self.current_user_id = None
        self._load_users()
        self._set_user_status(self._t("User '{username}' deleted.", username=username))

    def save_user_profile(self) -> bool:
        """Persist profile edits for the selected user."""
        # Validate the name and goal selection before updating.
        if not self.current_user_id:
            self._set_user_profile_status(self._t("Select a user to update the profile."), error=True)
            return False
        display_name = self.user_profile_name.strip()
        if not display_name:
            self._set_user_profile_status(self._t("Display name cannot be empty."), error=True)
            return False
        preferred_goal = None
        if self.user_profile_goal and self.user_profile_goal != self._no_goal_label:
            preferred_goal = self._goal_label_map.get(self.user_profile_goal)
            if not preferred_goal:
                self._set_user_profile_status(self._t("Select a valid goal option."), error=True)
                return False
        try:
            exercise_database.update_user_profile(
                user_id=self.current_user_id,
                display_name=display_name,
                preferred_goal=preferred_goal,
            )
        except sqlite3.DatabaseError as exc:
            self._set_user_profile_status(self._t("Database error: {error}", error=exc), error=True)
            return False
        self.current_user_display = display_name
        self._load_users()
        self._set_user_profile_status(self._t("Profile saved."))
        self._sync_recommendation_goal()
        return True

    def on_user_selected(self, username: str) -> None:
        """Update state when a user is selected from the spinner."""
        # Set current user and refresh dependent data.
        selected = next((u for u in self._users if u["username"] == username), None)
        if not selected:
            return
        self.current_user_id = selected["id"]
        self.current_user_display = selected.get("display_name") or selected["username"]
        self.user_spinner_text = selected["username"]
        self.user_profile_name = selected.get("display_name") or selected["username"]
        preferred_goal = selected.get("preferred_goal")
        if preferred_goal:
            goal_code = localization.goal_code_from_label(preferred_goal) or preferred_goal
            self.user_profile_goal = self._goal_code_label_map.get(goal_code, self._no_goal_label)
        else:
            self.user_profile_goal = self._no_goal_label
        self._set_user_status(self._t("User '{username}' selected.", username=username))
        self._load_history()
        self.go_home()

    def _split_exercises(self, raw: str) -> list[str]:
        """Split exercise input into a clean list."""
        # Support commas and newlines as separators.
        normalized = raw.replace("\n", ",")
        return [part.strip() for part in normalized.split(",") if part.strip()]

    def _known_exercise_names(self) -> set[str]:
        """Return a set of known exercise names for validation."""
        # Normalize names to lower-case for comparisons.
        return {record["name"].strip().lower() for record in self.records if record.get("name")}

    def _validate_history_exercises(self, exercises: list[str]) -> Optional[str]:
        """Validate exercise names against known records."""
        # Return a user-facing error string when unknown names appear.
        known = self._known_exercise_names()
        if not known:
            return None
        unknown = [
            name
            for name in exercises
            if self._resolve_exercise_name(name).strip().lower() not in known
        ]
        if unknown:
            return self._t("Unknown exercises: {names}", names=", ".join(unknown))
        return None

    def _parse_date_value(
        self,
        value: str,
        *,
        allow_empty: bool = False,
        allow_future: bool = True,
    ) -> Optional[str]:
        """Parse a date string and return ISO format."""
        # Raise helpful errors when input is missing or malformed.
        value = value.strip()
        if not value:
            if allow_empty:
                return None
            raise ValueError(self._t("Date is required (YYYY-MM-DD)."))
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            raise ValueError(self._t("Use YYYY-MM-DD format."))
        if not allow_future and parsed > date.today():
            raise FutureDateError(self._t("Workout date cannot be in the future."))
        return parsed.isoformat()

    def open_date_picker(self, target_input: Any) -> None:
        """Open the shared date picker for a given input widget."""
        # Seed the picker with the current input value if possible.
        if not target_input:
            return
        text_value = getattr(target_input, "text", "").strip()
        initial = None
        if text_value:
            try:
                initial = date.fromisoformat(text_value)
            except ValueError:
                initial = None
        DatePickerPopup(
            initial_date=initial,
            on_select=lambda selected: self._set_date_input(target_input, selected),
        ).open()

    def _set_date_input(self, target_input: Any, selected: date) -> None:
        """Write a chosen date into the target input."""
        # Confirm the change so the input feedback animation runs.
        if target_input:
            target_input.text = selected.isoformat()
            self.confirm_value_input(target_input)
            if self._is_history_date_input(target_input):
                self.apply_history_filter()

    def _is_history_date_input(self, target_input: Any) -> bool:
        """Return True if the input belongs to the history filter."""
        if not target_input:
            return False
        try:
            ids = self._history_screen().ids
        except Exception:
            return False
        return target_input is ids.start_date_input or target_input is ids.end_date_input

    def _set_history_status(self, message: str, *, error: bool = False, prominent: bool = False) -> None:
        """Update status banner in the history screen."""
        # Use red for errors and green for success messages.
        self.history_status_text = message
        self.history_status_color = (0.65, 0.16, 0.16, 1) if error else (0.14, 0.4, 0.2, 1)
        self.history_status_font_size = "18sp" if prominent else "15sp"

    def _reset_history_exercise_picker(self, ids: Optional[Any] = None) -> None:
        """Reset the history exercise picker to its default state."""
        # Clear filter text and restore the full option list.
        self.history_exercise_spinner_text = self._select_exercise_label
        self.history_exercise_filter = ""
        self._refresh_history_exercise_filtered_options()
        form_ids = ids or self._workout_form_ids()
        if form_ids and "history_exercise_filter_input" in form_ids:
            form_ids.history_exercise_filter_input.text = ""

    def _set_history_weight_value(self, name: str, value_text: str, unit_text: str) -> None:
        """Persist weight inputs entered in the workout log modal."""
        # Store raw values so validation happens on save.
        self._history_weight_values[name] = {"value": value_text.strip(), "unit": "kg"}

    def _clear_workout_weight_inputs(self, ids: Optional[Any] = None) -> None:
        """Remove dynamic weight inputs from the workout log modal."""
        # Reset stored weights and hide the container.
        form_ids = ids or self._workout_form_ids()
        if form_ids and "workout_weight_container" in form_ids:
            form_ids.workout_weight_container.clear_widgets()
        self.history_weight_visible = False
        self._history_weight_values = {}

    def refresh_workout_weight_inputs(self, exercises_text: str) -> None:
        """Rebuild weight inputs based on the exercises in the log form."""
        # Show inputs only for exercises that support external load.
        ids = self._workout_form_ids()
        if not ids or "workout_weight_container" not in ids:
            return
        exercises = self._split_exercises(exercises_text)
        current_names = {self._resolve_exercise_name(name) for name in exercises}
        if self._history_weight_values:
            self._history_weight_values = {
                key: value for key, value in self._history_weight_values.items() if key in current_names
            }
        container = ids.workout_weight_container
        container.clear_widgets()
        self.history_weight_visible = False

        for name in exercises:
            canonical_name = self._resolve_exercise_name(name)
            record = self._record_for_name(canonical_name)
            if not record or not record.get("supports_weight"):
                continue
            self.history_weight_visible = True
            stored = self._history_weight_values.get(canonical_name, {})
            default_value = self._format_weight_value(record.get("default_weight_value"))
            value_text = stored.get("value", default_value)
            unit_text = "kg"
            self._set_history_weight_value(canonical_name, value_text, unit_text)

            row = BoxLayout(orientation="horizontal", spacing=dp(6), size_hint_y=None, height=dp(30))
            row.add_widget(
                Label(
                    text=self._display_exercise_name(canonical_name),
                    color=(0.18, 0.18, 0.24, 1),
                    size_hint_x=0.45,
                    halign="left",
                    valign="middle",
                )
            )
            weight_input = TextInput(
                text=value_text,
                multiline=False,
                input_filter="float",
                size_hint_x=0.35,
            )
            weight_input.bind(
                on_text_validate=lambda instance, exercise=canonical_name: (
                    self._set_history_weight_value(exercise, instance.text, "kg")
                )
            )
            weight_input.bind(
                on_focus=lambda instance, focused, exercise=canonical_name: (
                    self._set_history_weight_value(exercise, instance.text, "kg") if not focused else None
                )
            )
            row.add_widget(weight_input)
            row.add_widget(
                Label(
                    text="kg",
                    color=(0.2, 0.2, 0.25, 1),
                    size_hint_x=0.2,
                    halign="center",
                    valign="middle",
                )
            )
            container.add_widget(row)

    def _reset_workout_log_form(self, *, clear_status: bool = True) -> None:
        """Clear workout log inputs and restore defaults."""
        # Keep date prefilled and status optionally cleared.
        ids = self._workout_form_ids()
        if not ids:
            return
        ids.duration_input.text = ""
        ids.exercises_input.text = ""
        ids.total_sets_input.text = ""
        self._clear_workout_weight_inputs(ids)
        self._reset_history_exercise_picker(ids)
        self.workout_goal_spinner_text = self._default_workout_goal_label()
        if clear_status:
            self._set_history_status("")
        self._prefill_workout_date()

    def _clear_workout_log_modal(self, *_: Any) -> None:
        """Clear the cached workout log modal reference."""
        # Ensure next open creates a fresh modal instance.
        self._workout_log_modal = None
        self.history_weight_visible = False
        self._history_weight_values = {}

    def _clear_goal_prompt_modal(self, *_: Any) -> None:
        """Clear the cached goal prompt modal reference."""
        # Ensure next open creates a fresh modal instance.
        self._goal_prompt_modal = None

    def open_workout_log_modal(self) -> None:
        """Open the workout log modal, resetting form state."""
        # Require a user selection before allowing logging.
        if not self._require_user():
            return
        if self._workout_log_modal is not None:
            try:
                self._workout_log_modal.dismiss()
            except Exception:
                pass
        modal = WorkoutLogModal()
        modal.bind(on_dismiss=self._clear_workout_log_modal)
        self._workout_log_modal = modal
        self._reset_workout_log_form(clear_status=True)
        modal.open()

    def _dismiss_workout_log_modal(self) -> None:
        """Dismiss the workout log modal if it is open."""
        # Guard against missing modal instances.
        if self._workout_log_modal is None:
            return
        try:
            self._workout_log_modal.dismiss()
        except Exception:
            pass

    def _dismiss_goal_prompt_modal(self) -> None:
        """Dismiss the goal prompt modal if it is open."""
        # Guard against missing modal instances.
        if self._goal_prompt_modal is None:
            return
        try:
            self._goal_prompt_modal.dismiss()
        except Exception:
            pass

    def open_goal_prompt(self) -> None:
        """Open the goal prompt modal with a default selection."""
        # Suggest a preferred goal when none is set.
        if not self.current_user_id or not self.user_goal_options:
            return
        if self._goal_prompt_modal is not None:
            try:
                self._goal_prompt_modal.dismiss()
            except Exception:
                pass
        if self.user_profile_goal == self._no_goal_label:
            preferred = self._preferred_goal_label()
            if preferred and preferred in self.user_goal_options:
                self.user_profile_goal = preferred
        self._set_user_profile_status("")
        modal = GoalPromptModal()
        modal.bind(on_dismiss=self._clear_goal_prompt_modal)
        self._goal_prompt_modal = modal
        modal.open()

    def skip_goal_prompt(self) -> None:
        """Skip setting a goal and close the prompt."""
        # Explicitly mark the profile goal as unset.
        self.user_profile_goal = self._no_goal_label
        self._set_user_profile_status("")
        self._dismiss_goal_prompt_modal()

    def add_history_exercise_from_menu(self) -> None:
        """Add the selected exercise from the dropdown to the log."""
        # Prevent duplicates when adding exercises via the picker.
        ids = self._workout_form_ids()
        if not ids:
            return
        selected = ids.history_exercise_spinner.text.strip()
        if not selected or selected in {self._select_exercise_label, self._no_matches_label, self._no_exercises_label}:
            return
        existing = self._split_exercises(ids.exercises_input.text)
        existing_lower = {name.lower() for name in existing}
        if selected.lower() in existing_lower:
            self._set_history_status(self._t("{selected} is already listed.", selected=selected))
            return
        if ids.exercises_input.text.strip():
            ids.exercises_input.text = ids.exercises_input.text.rstrip() + "\n" + selected
        else:
            ids.exercises_input.text = selected
        self.confirm_value_input(ids.exercises_input)
        self.refresh_workout_weight_inputs(ids.exercises_input.text)
        self._set_history_status(self._t("Added {selected}.", selected=selected))
        self.history_exercise_spinner_text = self._select_exercise_label

    def _load_history(self, *_: Any) -> None:
        """Load workout history entries and update the history UI."""
        # Fetch data from the database and rebuild cards.
        try:
            history_screen = self._history_screen()
        except Exception:
            return

        if not self.current_user_id:
            history_list = history_screen.ids.history_list
            history_list.clear_widgets()
            self._set_history_status(self._t("Select or register a user to see history."), error=False)
            self._load_stats(clear=True)
            return

        try:
            history_entries = exercise_database.fetch_workout_history(
                self.current_user_id,
                start_date=self.history_start,
                end_date=self.history_end,
            )
        except sqlite3.DatabaseError as exc:
            self._set_history_status(self._t("Database error: {error}", error=exc), error=True)
            return

        cards: list[WorkoutCard] = []
        for entry in history_entries:
            exercise_names = entry.get("exercises", []) or []
            display_names = [self._display_exercise_name(name) for name in exercise_names]
            exercises_display = ", ".join(display_names) if display_names else self._t("No exercises recorded")
            attempts = entry.get("exercise_attempts") or []
            if attempts:
                attempt_labels = []
                for att in attempts:
                    raw_status = att.get("status", "completed")
                    status = self._t("Completed") if raw_status == "completed" else self._t("Skipped")
                    weight_label = self._format_weight_label(att.get("weight_value"), att.get("weight_unit"))
                    display_name = self._display_exercise_name(att.get("name", self._t("Exercise")))
                    if weight_label != "—":
                        attempt_labels.append(f"{display_name} ({status}, {weight_label})")
                    else:
                        attempt_labels.append(f"{display_name} ({status})")
                attempts_display = self._t("Attempts: {attempts}", attempts=", ".join(attempt_labels))
            else:
                attempts_display = self._t("Attempts: none recorded")
            goal_value = entry.get("goal") or ""
            goal_code = localization.goal_code_from_label(goal_value) or goal_value
            if goal_value:
                goal_display = self._goal_code_label_map.get(goal_code, goal_value)
            else:
                goal_display = "—"
            sets_display = str(entry.get("total_sets_completed") or 0)
            duration_minutes = entry.get("duration_minutes") or 0
            duration_seconds = entry.get("duration_seconds")
            if duration_seconds is not None:
                duration_display = self._t(
                    "{minutes} min ({seconds}s)",
                    minutes=duration_minutes,
                    seconds=duration_seconds,
                )
            else:
                duration_display = self._t("{minutes} min", minutes=duration_minutes)
            card = WorkoutCard(
                date_display=entry["performed_at"],
                duration_display=duration_display,
                exercises_display=exercises_display,
                goal_display=goal_display,
                sets_display=sets_display,
                attempts_display=attempts_display,
            )
            cards.append(card)
        history_list = history_screen.ids.history_list
        history_list.clear_widgets()
        for card in cards:
            history_list.add_widget(card)
        if cards:
            self._set_history_status(
                self._t("{count} workout(s) loaded.", count=len(cards))
            )
        else:
            self._set_history_status(self._t("No workouts in this date range."), error=False)
        self._load_stats()

    def apply_history_filter(self) -> None:
        """Apply date filters to the history list."""
        # Parse filter inputs and reload history entries.
        ids = self._history_screen().ids
        try:
            self.history_start = self._parse_date_value(ids.start_date_input.text, allow_empty=True)
            self.history_end = self._parse_date_value(ids.end_date_input.text, allow_empty=True)
        except ValueError as exc:
            self._set_history_status(str(exc), error=True)
            return
        self._load_history()

    def clear_history_filter(self) -> None:
        """Clear history date filters and reload history."""
        # Reset filter fields and state.
        ids = self._history_screen().ids
        ids.start_date_input.text = ""
        ids.end_date_input.text = ""
        self.history_start = None
        self.history_end = None
        self._set_history_status(self._t("Filters cleared."))
        self._load_history()

    def handle_add_workout(self) -> None:
        """Validate workout form inputs and log a session."""
        # Ensure required fields are present and valid.
        if not self.current_user_id:
            self._set_history_status(self._t("Select or register a user first."), error=True)
            return

        ids = self._workout_form_ids()
        if not ids:
            self._set_history_status(self._t("Open the workout form to log a session."), error=True)
            return
        try:
            workout_date = self._parse_date_value(
                ids.workout_date_input.text,
                allow_empty=False,
                allow_future=False,
            )
        except FutureDateError as exc:
            self._set_history_status(str(exc), error=True, prominent=True)
            return
        except ValueError as exc:
            self._set_history_status(str(exc), error=True)
            return

        duration_raw = ids.duration_input.text.strip()
        try:
            duration_minutes = int(duration_raw)
            if duration_minutes <= 0:
                raise ValueError
        except ValueError:
            self._set_history_status(self._t("Duration must be a positive number of minutes."), error=True)
            return

        exercises = self._split_exercises(ids.exercises_input.text)
        if not exercises:
            self._set_history_status(self._t("Add at least one exercise."), error=True)
            return
        validation_error = self._validate_history_exercises(exercises)
        if validation_error:
            self._set_history_status(validation_error, error=True)
            return

        goal_label = ids.workout_goal_spinner.text.strip()
        goal = None
        if goal_label and goal_label != self._no_goal_label:
            goal = self._goal_label_map.get(goal_label) or goal_label

        sets_raw = ids.total_sets_input.text.strip()
        total_sets_completed = None
        if sets_raw:
            try:
                total_sets_completed = int(sets_raw)
                if total_sets_completed < 0:
                    raise ValueError
            except ValueError:
                self._set_history_status(self._t("Total sets must be 0 or greater."), error=True)
                return

        exercise_weights = []
        canonical_exercises = [self._resolve_exercise_name(name) for name in exercises]
        for name in canonical_exercises:
            record = self._record_for_name(name)
            if record and record.get("supports_weight"):
                stored = self._history_weight_values.get(name)
                if stored:
                    value_text = stored.get("value", "")
                    unit_text = stored.get("unit", record.get("default_weight_unit") or "kg")
                else:
                    value_text = self._format_weight_value(record.get("default_weight_value"))
                    unit_text = record.get("default_weight_unit") or "kg"
                try:
                    weight_value = self._parse_optional_float(value_text)
                except ValueError as exc:
                    self._set_history_status(
                        self._t("Weight for {name}: {error}", name=self._display_exercise_name(name), error=exc),
                        error=True,
                    )
                    return
                weight_unit = self._normalize_weight_unit(unit_text) or "kg"
                if weight_value is None:
                    weight_unit = None
                exercise_weights.append((name, weight_value, weight_unit))
            else:
                exercise_weights.append((name, None, None))

        try:
            exercise_database.log_workout(
                user_id=self.current_user_id,
                performed_at=workout_date,
                duration_minutes=duration_minutes,
                exercises=canonical_exercises,
                goal=goal,
                total_sets_completed=total_sets_completed,
                exercise_weights=exercise_weights,
            )
        except (ValueError, sqlite3.DatabaseError) as exc:
            self._set_history_status(self._t(str(exc)), error=True)
            return

        self._set_history_status(self._t("Workout saved."))
        self._reset_workout_log_form(clear_status=False)
        self._load_history()
        self._dismiss_workout_log_modal()

    def _load_stats(self, *, clear: bool = False) -> None:
        """Load and display workout statistics for the user."""
        # Optionally clear stats when no user is selected.
        if clear or not self.current_user_id:
            self.stats_total_workouts = "0"
            self.stats_total_minutes = "0"
            self.stats_total_weight = "—"
            self.stats_top_exercise = "—"
            return
        try:
            stats = exercise_database.fetch_workout_stats(
                self.current_user_id,
                start_date=self.history_start,
                end_date=self.history_end,
            )
        except sqlite3.DatabaseError as exc:
            self._set_history_status(
                self._t("Database error while loading stats: {error}", error=exc),
                error=True,
            )
            return

        self.stats_total_workouts = str(stats.get("total_workouts", 0))
        self.stats_total_minutes = str(stats.get("total_minutes", 0))
        total_kg = float(stats.get("total_weight_kg") or 0)
        total_lb = float(stats.get("total_weight_lb") or 0)
        if total_lb:
            total_kg += total_lb * 0.453592
        if total_kg:
            self.stats_total_weight = f"{self._format_weight_value(total_kg)} kg"
        else:
            self.stats_total_weight = "—"
        top = stats.get("top_exercise")
        if top:
            count = stats.get("top_exercise_count", 0)
            self.stats_top_exercise = f"{self._display_exercise_name(top)} ({count}x)"
        else:
            self.stats_top_exercise = "—"

    # --- Recommendation system ---
    def _set_rec_status(self, message: str, *, error: bool = False) -> None:
        """Update status banner in the recommendation screen."""
        # Use red for errors and green for success messages.
        self.rec_status_text = message
        self.rec_status_color = (0.65, 0.16, 0.16, 1) if error else (0.14, 0.4, 0.2, 1)
        self.rec_status_is_error = error

    def _plan_goal_label(self) -> str:
        """Return a single goal label for the current plan."""
        # Summarize goals to detect mixed-goal plans.
        labels = {item.get("goal_label") for item in self.rec_plan if item.get("goal_label")}
        if not labels:
            return ""
        if len(labels) == 1:
            return labels.pop()
        return self._t("Multiple goals")

    def _rest_seconds_for_plan(self) -> int:
        """Return configured rest seconds with safe fallback."""
        # Guard against invalid user input.
        try:
            return int(getattr(self, "live_rest_seconds", 30) or 0)
        except (TypeError, ValueError):
            return 30

    def _minutes_from_seconds(self, total_seconds: int) -> int:
        """Convert seconds to rounded-up minutes."""
        # Round up to avoid under-reporting time.
        if total_seconds <= 0:
            return 0
        return int((total_seconds + 59) // 60)

    def _estimate_exercise_seconds(self, record: dict[str, Any]) -> int:
        """
        Estimate total time for one exercise including rest between sets.

        - If recommended_time_seconds is available, treat it as per-set time.
        - Else, assume each rep ~4 seconds with a 20s minimum per set.
        - Else, assume 30s per set when only sets are provided.
        - Fallback to 5 minutes if no volume info exists.
        """
        # Use conservative fallbacks when data is missing.
        try:
            time_seconds = record.get("time_seconds")
            sets = record.get("sets")
            reps = record.get("reps")
            if not time_seconds and not sets and not reps:
                return 5 * 60
            rest_seconds = int(getattr(self, "live_rest_seconds", 30) or 0)
            set_count = int(sets) if sets else 1
            if time_seconds:
                per_set = max(10, int(time_seconds))
            elif reps:
                per_set = max(20, int(reps) * 4)
            else:
                per_set = 30
            total = set_count * per_set
            if set_count > 1:
                total += (set_count - 1) * rest_seconds
            return max(total, per_set)
        except Exception:
            return 5 * 60

    def _estimate_minutes(self, record: dict[str, Any]) -> int:
        """
        Estimate training time for an exercise.

        Scoring logic (documented for transparency):
        - Include rest between sets using the configured rest duration.
        - Use per-set time when recommended_time_seconds is provided.
        - Else, assume each rep ~4 seconds with a 20s minimum per set.
        - Fallback to 5 minutes if no volume info exists.
        """
        # Convert estimated seconds into whole minutes for UI display.
        total_seconds = RootWidget._estimate_exercise_seconds(self, record)
        return max(1, RootWidget._minutes_from_seconds(self, total_seconds))

    def _estimate_plan_seconds(self, plan_items: Sequence[dict[str, Any]]) -> int:
        """Estimate total plan duration including rest breaks."""
        # Sum exercise estimates and insert rest between items.
        if not plan_items:
            return 0
        rest_seconds = self._rest_seconds_for_plan()
        total_seconds = 0
        for item in plan_items:
            estimated_seconds = item.get("estimated_seconds")
            if isinstance(estimated_seconds, (int, float)):
                total_seconds += int(estimated_seconds)
            else:
                total_seconds += self._estimate_exercise_seconds(item)
        if len(plan_items) > 1:
            total_seconds += (len(plan_items) - 1) * rest_seconds
        return total_seconds

    def _recency_days_map(self) -> dict[str, int]:
        """Return a mapping of exercise name to days since last performed for current user."""
        # Build a first-hit map from recent workout history.
        if not self.current_user_id:
            return {}
        rows = exercise_database.fetch_recent_exercise_usage(self.current_user_id, limit=200)
        recency: dict[str, int] = {}
        today = date.today()
        for name, performed_at in rows:
            if name in recency:
                continue
            try:
                performed_date = date.fromisoformat(performed_at)
                recency[name] = (today - performed_date).days
            except Exception:
                continue
        return recency

    def _score_recommendation(self, record: dict[str, Any], recency_days: Optional[int]) -> float:
        """
        Recommendation score formula (documented per requirement):
        score = suitability_rating
                + recency_bonus
        where:
            recency_bonus = +2.0 if never done
                           +1.0 if >14 days ago
                           +0.5 if between 7-14 days
                           -1.0 if done within last 3 days
                           0 otherwise
        """
        # Apply the recency bonus to the base rating.
        base = float(record.get("rating", 0))
        if recency_days is None:
            recency_bonus = 2.0
        elif recency_days > 14:
            recency_bonus = 1.0
        elif recency_days >= 7:
            recency_bonus = 0.5
        elif recency_days <= 3:
            recency_bonus = -1.0
        else:
            recency_bonus = 0.0
        return round(base + recency_bonus, 2)

    def handle_generate_recommendations(self) -> None:
        """Generate recommendations based on goal and time limit."""
        # Validate inputs before running recommendation logic.
        if not self._require_user():
            return
        if not self.rec_goal_spinner_text:
            self._set_rec_status(self._t("Choose a goal."), error=True)
            return
        try:
            max_minutes = int(self._recommend_screen().ids.rec_max_time.text.strip() or "0")
            if max_minutes <= 0:
                raise ValueError
        except ValueError:
            self._set_rec_status(self._t("Enter a positive max time (minutes)."), error=True)
            return

        self.rec_max_minutes_text = str(max_minutes)
        goal_code = self._goal_label_map.get(self.rec_goal_spinner_text)
        if not goal_code:
            self._set_rec_status(self._t("Unknown goal selection."), error=True)
            return

        recency_map = self._recency_days_map()
        recommendations = []
        for record in self.records:
            if record["goal"] != goal_code:
                continue
            if any(item["name"] == record["name"] for item in self.rec_plan):
                continue
            est_seconds = self._estimate_exercise_seconds(record)
            est_minutes = self._minutes_from_seconds(est_seconds)
            recency_days = recency_map.get(record["name"])
            score = self._score_recommendation(
                {"rating": float(record.get("rating", 0))}, recency_days
            )
            supports_weight = bool(record.get("supports_weight"))
            default_weight_value = record.get("default_weight_value")
            default_weight_unit = record.get("default_weight_unit") or ("kg" if supports_weight else None)
            recommendations.append(
                {
                    "name": record["name"],
                    "display_name": record.get("display_name", record["name"]),
                    "icon": record.get("icon", ""),
                    "icon_source": record.get("icon_source", ""),
                    "description": record["description"],
                    "execution_instructions": record.get("execution_instructions", ""),
                    "muscle_group": record["muscle_group"],
                    "equipment": record["equipment"],
                    "supports_weight": supports_weight,
                    "default_weight_value": default_weight_value,
                    "default_weight_unit": default_weight_unit,
                    "goal_label": record["goal_label"],
                    "suitability": record["suitability_display"],
                    "recommendation": record["recommendation"],
                    "sets": record.get("sets"),
                    "reps": record.get("reps"),
                    "time_seconds": record.get("time_seconds"),
                    "estimated_minutes": str(est_minutes),
                    "estimated_seconds": est_seconds,
                    "score": score,
                    "score_display": str(score),
                    "show_details": False,
                }
            )

        recommendations.sort(key=lambda r: (-r["score"], r.get("display_name") or r["name"]))
        self.rec_recommendations = recommendations
        self._recommend_screen().ids.rec_list.data = recommendations
        self._set_rec_status(self._t("{count} exercises recommended.", count=len(recommendations)))
        # Reset plan only if the selected goal conflicts with the existing plan.
        plan_goal = self._plan_goal_label()
        if plan_goal and plan_goal != self._t("Multiple goals") and plan_goal != self.rec_goal_spinner_text:
            self._reset_plan(silent=True)

    def _find_recommendation(self, name: str) -> Optional[dict[str, Any]]:
        """Find a recommendation entry by exercise name."""
        # Search the current recommendation list for a match.
        return next((rec for rec in self.rec_recommendations if rec["name"] == name), None)

    def _clear_recommendation_detail_modal(self, *_: Any) -> None:
        """Clear the cached recommendation detail modal reference."""
        # Ensure next open creates a fresh modal instance.
        self._recommendation_detail_modal = None

    def _clear_browse_detail_modal(self, *_: Any) -> None:
        """Clear the cached browse detail modal reference."""
        # Ensure next open creates a fresh modal instance.
        self._browse_detail_modal = None

    def _find_browse_entry(self, name: str) -> Optional[dict[str, Any]]:
        """Find a browse list entry by exercise name."""
        # Search the active browse list for a match.
        browse_data = self._browse_screen().ids.exercise_list.data
        return next((entry for entry in browse_data if entry.get("name") == name), None)

    def open_browse_details(self, name: str) -> None:
        """Open the browse detail modal for an exercise."""
        # Populate the modal from the browse list data.
        entry = self._find_browse_entry(name)
        if not entry:
            return
        if self._browse_detail_modal is not None:
            try:
                self._browse_detail_modal.dismiss()
            except Exception:
                pass
        modal = ExerciseDetailsModal()
        modal.show_add_button = False
        modal.exercise_name = entry.get("display_name", entry.get("name", ""))
        modal.exercise_key = entry.get("name", "")
        modal.description = entry.get("description", "")
        modal.execution_instructions = entry.get("execution_instructions", "")
        modal.muscle_group = entry.get("muscle_group", "")
        modal.equipment = entry.get("equipment", "")
        modal.goal_label = entry.get("goal_label", "")
        modal.suitability = entry.get("suitability_value") or entry.get("suitability_display", "")
        estimated = entry.get("estimated_minutes")
        modal.estimated_minutes = str(estimated) if estimated not in (None, "") else ""
        score_display = entry.get("score_display")
        modal.score_display = str(score_display) if score_display not in (None, "") else ""
        modal.recommendation = entry.get("recommendation", "")
        modal.sets_display = entry.get("sets_display", "—")
        modal.reps_display = entry.get("reps_display", "—")
        modal.time_display = entry.get("time_display", "—")
        modal.bind(on_dismiss=self._clear_browse_detail_modal)
        self._browse_detail_modal = modal
        modal.open()

    def open_recommendation_details(self, name: str) -> None:
        """Open the recommendation detail modal for an exercise."""
        # Populate the modal from the recommendation data.
        rec = self._find_recommendation(name)
        if not rec:
            return
        if self._recommendation_detail_modal is not None:
            try:
                self._recommendation_detail_modal.dismiss()
            except Exception:
                pass
        modal = ExerciseDetailsModal()
        modal.show_add_button = True
        modal.exercise_name = rec.get("display_name", rec.get("name", ""))
        modal.exercise_key = rec.get("name", "")
        modal.description = rec.get("description", "")
        modal.execution_instructions = rec.get("execution_instructions", "")
        modal.muscle_group = rec.get("muscle_group", "")
        modal.equipment = rec.get("equipment", "")
        modal.goal_label = rec.get("goal_label", "")
        modal.suitability = rec.get("suitability", "")
        estimated = rec.get("estimated_minutes")
        score_display = rec.get("score_display")
        modal.estimated_minutes = str(estimated) if estimated is not None else ""
        modal.score_display = str(score_display) if score_display is not None else ""
        modal.recommendation = rec.get("recommendation", "")
        sets = rec.get("sets")
        reps = rec.get("reps")
        time_seconds = rec.get("time_seconds")
        modal.sets_display = str(sets) if sets is not None else "—"
        modal.reps_display = str(reps) if reps is not None else "—"
        if time_seconds is None:
            modal.time_display = "—"
        else:
            modal.time_display = self._t("{seconds} sec", seconds=time_seconds)
        modal.bind(on_dismiss=self._clear_recommendation_detail_modal)
        self._recommendation_detail_modal = modal
        modal.open()

    def toggle_recommendation_details(self, name: str) -> None:
        """Toggle the detail expansion state for a recommendation."""
        # Preserve per-item toggle state in the list data.
        rec = self._find_recommendation(name)
        if not rec:
            return
        # flip detail visibility for this item
        current = bool(rec.get("show_details"))
        for r in self.rec_recommendations:
            if r["name"] == name:
                r["show_details"] = not current
            else:
                r["show_details"] = bool(r.get("show_details", False))
        self._recommend_screen().ids.rec_list.data = self.rec_recommendations
        self._set_rec_status(self._t("Details toggled."))

    def add_recommendation_to_plan(self, name: str) -> None:
        """Add a recommendation to the workout plan."""
        # Avoid duplicates and carry over recommendation metadata.
        rec = self._find_recommendation(name)
        if not rec:
            return
        if any(item["name"] == name for item in self.rec_plan):
            self._set_rec_status(self._t("{name} is already in the plan.", name=rec.get("display_name", name)), error=True)
            return
        icon_source = rec.get("icon_source") or self._resolve_icon_source(rec.get("icon", "") or rec.get("name", ""))
        supports_weight = bool(rec.get("supports_weight"))
        weight_value = rec.get("default_weight_value")
        weight_unit = rec.get("default_weight_unit") or ("kg" if supports_weight else None)
        plan_item = {
            "name": rec["name"],
            "display_name": rec.get("display_name", rec["name"]),
            "icon": rec.get("icon", ""),
            "icon_source": icon_source,
            "execution_instructions": rec.get("execution_instructions", ""),
            "muscle_group": rec.get("muscle_group", ""),
            "equipment": rec.get("equipment", ""),
            "supports_weight": supports_weight,
            "weight_value": weight_value,
            "weight_unit": weight_unit,
            "goal_label": rec.get("goal_label", ""),
            "sets": rec.get("sets"),
            "reps": rec.get("reps"),
            "time_seconds": rec.get("time_seconds"),
            "recommendation": rec.get("recommendation", ""),
            "estimated_minutes": rec["estimated_minutes"],
            "estimated_seconds": rec.get("estimated_seconds"),
            "display": self._t(
                "{name} ({minutes} min)",
                name=rec.get("display_name", rec["name"]),
                minutes=rec["estimated_minutes"],
            ),
        }
        self.rec_plan.append(plan_item)
        self._refresh_recommendation_view()
        self._set_rec_status(self._t("Added {name} to plan.", name=rec.get("display_name", name)))
        # Remove from recommendations list when selected.
        self.rec_recommendations = [r for r in self.rec_recommendations if r["name"] != name]
        self._recommend_screen().ids.rec_list.data = self.rec_recommendations

    def _refresh_recommendation_view(self) -> None:
        """Rebuild the planned exercise list view."""
        # Map plan items into the KV list data structure.
        rv = self._recommend_screen().ids.rec_plan_list
        rv.data = [
            {
                "name": item["name"],
                "icon_source": item.get("icon_source")
                or self._resolve_icon_source(item.get("icon", "") or item.get("name", "")),
                "display": self._t(
                    "{name} ({minutes} min)",
                    name=item.get("display_name", item["name"]),
                    minutes=item["estimated_minutes"],
                ),
                "index": str(idx),
                "weight_value_text": self._format_weight_value(item.get("weight_value")),
                "weight_unit_text": item.get("weight_unit") or "kg",
                "weight_visible": bool(item.get("supports_weight")),
            }
            for idx, item in enumerate(self.rec_plan)
        ]
        self._validate_plan_time()
        rv.refresh_from_data()

    def update_plan_item_weight(self, name: str, value_text: str, unit_text: str) -> None:
        """Update the stored weight for a planned exercise."""
        # Persist user edits without disturbing plan order.
        item = next((entry for entry in self.rec_plan if entry.get("name") == name), None)
        if not item or not item.get("supports_weight"):
            return
        unit = "kg"
        value = None
        if value_text.strip():
            try:
                value = float(value_text)
                if value <= 0:
                    raise ValueError
            except ValueError:
                self._set_rec_status(self._t("Weight must be a positive number."), error=True)
                return
        item["weight_value"] = value
        item["weight_unit"] = unit

    def _recalculate_recommendation_times(self) -> None:
        """Recompute time estimates for recommendations and plan items."""
        # Refresh UI data so estimated times stay accurate.
        if self.rec_recommendations:
            for rec in self.rec_recommendations:
                est_seconds = self._estimate_exercise_seconds(rec)
                rec["estimated_seconds"] = est_seconds
                rec["estimated_minutes"] = str(self._minutes_from_seconds(est_seconds))
            try:
                rec_list = self._recommend_screen().ids.rec_list
                rec_list.data = self.rec_recommendations
                rec_list.refresh_from_data()
            except Exception:
                pass
        if self.rec_plan:
            for item in self.rec_plan:
                est_seconds = self._estimate_exercise_seconds(item)
                item["estimated_seconds"] = est_seconds
                item["estimated_minutes"] = str(self._minutes_from_seconds(est_seconds))
                item["display"] = self._t(
                    "{name} ({minutes} min)",
                    name=item.get("display_name", item["name"]),
                    minutes=item["estimated_minutes"],
                )
            self._refresh_recommendation_view()
        else:
            self._validate_plan_time()

    def move_plan_item(self, name: str, direction: int) -> None:
        """Move a plan item up or down by one position."""
        # Reorder in-place and refresh the view.
        for idx, item in enumerate(self.rec_plan):
            if item["name"] == name:
                new_idx = max(0, min(len(self.rec_plan) - 1, idx + direction))
                if new_idx != idx:
                    self.rec_plan.insert(new_idx, self.rec_plan.pop(idx))
                    self._set_rec_status(self._t("Moved {name}.", name=item.get("display_name", name)))
                    self._refresh_recommendation_view()
                return

    def remove_plan_item(self, name: str) -> None:
        """Remove a plan item and optionally restore it to recommendations."""
        # Keep recommendation list consistent with the current goal.
        self.rec_plan = [item for item in self.rec_plan if item["name"] != name]
        self._set_rec_status(self._t("Removed {name} from plan.", name=self._display_exercise_name(name)))
        self._refresh_recommendation_view()
        # Return the exercise to recommendations list in sorted order if it fits the current goal.
        if self.rec_goal_spinner_text:
            goal_code = self._goal_label_map.get(self.rec_goal_spinner_text)
            match = next((r for r in self.records if r["name"] == name and r["goal"] == goal_code), None)
            if match:
                est_seconds = self._estimate_exercise_seconds(match)
                est_minutes = self._minutes_from_seconds(est_seconds)
                recency_map = self._recency_days_map()
                recency_days = recency_map.get(match["name"])
                score = self._score_recommendation({"rating": float(match.get("rating", 0))}, recency_days)
                self.rec_recommendations.append(
                    {
                        "name": match["name"],
                        "display_name": match.get("display_name", match["name"]),
                        "description": match["description"],
                        "execution_instructions": match.get("execution_instructions", ""),
                        "muscle_group": match["muscle_group"],
                        "equipment": match["equipment"],
                        "icon": match.get("icon", ""),
                        "icon_source": match.get("icon_source", ""),
                        "supports_weight": bool(match.get("supports_weight")),
                        "default_weight_value": match.get("default_weight_value"),
                        "default_weight_unit": match.get("default_weight_unit") or (
                            "kg" if match.get("supports_weight") else None
                        ),
                        "goal_label": match["goal_label"],
                        "suitability": match["suitability_display"],
                        "recommendation": match["recommendation"],
                        "sets": match.get("sets"),
                        "reps": match.get("reps"),
                        "time_seconds": match.get("time_seconds"),
                        "estimated_minutes": str(est_minutes),
                        "estimated_seconds": est_seconds,
                        "score": score,
                        "score_display": str(score),
                        "show_details": False,
                    }
                )
                self.rec_recommendations.sort(
                    key=lambda r: (-r["score"], r.get("display_name") or r["name"])
                )
                self._recommend_screen().ids.rec_list.data = self.rec_recommendations

    def _reset_plan(self, *, silent: bool = False) -> None:
        """Clear the recommendation plan data and UI."""
        # Reset list data and status messaging.
        self.rec_plan = []
        self.rec_total_minutes = "0"
        rv = self._recommend_screen().ids.rec_plan_list
        rv.data = []
        rv.refresh_from_data()
        if not silent:
            self._set_rec_status(self._t("Plan cleared."))

    def clear_recommendation_plan(self) -> None:
        """Clear the plan via the public action."""
        # Provide a user-facing wrapper around _reset_plan.
        self._reset_plan(silent=False)

    def on_rec_max_time_change(self, value: str) -> None:
        """Update max time input and refresh plan timing feedback."""
        # Keep the display and validation in sync with user edits.
        self.rec_max_minutes_text = value.strip()
        self._validate_plan_time()

    def _validate_plan_time(self) -> bool:
        """Validate plan time against the configured max minutes."""
        # Update status messaging when outside the target range.
        total_seconds = self._estimate_plan_seconds(self.rec_plan)
        total_minutes = self._minutes_from_seconds(total_seconds)
        self.rec_total_minutes = str(total_minutes)
        try:
            target = int(self.rec_max_minutes_text or "0")
        except ValueError:
            target = 0
        if not self.rec_plan:
            return True
        if not target:
            return True
        delta = total_minutes - target
        rest_note = self._t(
            "Includes {seconds}s rest between sets/exercises.",
            seconds=self._rest_seconds_for_plan(),
        )
        if abs(delta) <= 5:
            self._set_rec_status(
                self._t(
                    "Plan ready. Total {total} min vs {target} min target (±5 min). {rest_note}",
                    total=total_minutes,
                    target=target,
                    rest_note=rest_note,
                )
            )
            return True
        if delta > 5:
            self._set_rec_status(
                self._t(
                    "Plan time {total} min exceeds target {target} min by {delta} min. {rest_note}",
                    total=total_minutes,
                    target=target,
                    delta=delta,
                    rest_note=rest_note,
                ),
                error=True,
            )
            return False
        self._set_rec_status(
            self._t(
                "Plan time {total} min is {delta} min below target {target} min. {rest_note}",
                total=total_minutes,
                delta=abs(delta),
                target=target,
                rest_note=rest_note,
            ),
            error=True,
        )
        return False

    def handle_start_training(self) -> None:
        """Start live mode using the current plan."""
        # Validate plan and build the session exercise list.
        if not self._require_user():
            return
        if not self.rec_plan:
            self._set_rec_status(self._t("Add at least one exercise to the plan."), error=True)
            return
        if not self._validate_plan_time():
            return
        session_plan: list[dict[str, Any]] = []
        missing: list[str] = []
        name_to_record = {r["name"]: r for r in self.records}
        for item in self.rec_plan:
            record = name_to_record.get(item["name"])
            if not record:
                missing.append(item.get("display_name", item["name"]))
                continue
            session_plan.append(
                {
                    "name": record["name"],
                    "display_name": record.get("display_name", record["name"]),
                    "icon": record.get("icon", ""),
                    "icon_source": record.get("icon_source", ""),
                    "description": record.get("description", ""),
                    "execution_instructions": record.get("execution_instructions", ""),
                    "muscle_group": record.get("muscle_group", ""),
                    "equipment": record.get("equipment", ""),
                    "supports_weight": bool(record.get("supports_weight")),
                    "weight_value": item.get("weight_value")
                    if item.get("supports_weight")
                    else record.get("default_weight_value"),
                    "weight_unit": item.get("weight_unit")
                    if item.get("supports_weight")
                    else record.get("default_weight_unit") or ("kg" if record.get("supports_weight") else None),
                    "sets": record.get("sets") or item.get("sets") or 3,
                    "reps": record.get("reps") or item.get("reps"),
                    "time_seconds": record.get("time_seconds") or item.get("time_seconds"),
                    "recommendation": record.get("recommendation", ""),
                    "estimated_minutes": item.get("estimated_minutes", "0"),
                }
            )
        if missing:
            self._set_rec_status(self._t("Missing data for: {names}", names=", ".join(missing)), error=True)
            return
        if not session_plan:
            self._set_rec_status(self._t("Could not start live mode. Add exercises again."), error=True)
            return
        self._begin_live_session(session_plan)
        try:
            self.ids.screen_manager.current = "live"
        except Exception:
            pass
        self._set_rec_status(
            self._t("Live mode started with {count} exercise(s).", count=len(session_plan)),
            error=False,
        )

    def _parse_optional_int(self, value: str) -> Optional[int]:
        """Parse a positive integer or return None."""
        # Use ValueError to signal invalid input to the caller.
        value = value.strip()
        if not value:
            return None
        try:
            parsed = int(value)
            if parsed <= 0:
                raise ValueError
            return parsed
        except ValueError:
            raise ValueError(self._t("Enter positive numbers only."))

    def _parse_optional_float(self, value: str) -> Optional[float]:
        """Parse a positive float or return None."""
        # Use ValueError to signal invalid input to the caller.
        value = value.strip()
        if not value:
            return None
        try:
            parsed = float(value)
            if parsed <= 0:
                raise ValueError
            return parsed
        except ValueError:
            raise ValueError(self._t("Enter positive numbers only."))

    def _set_status(self, message: str, *, error: bool = False) -> None:
        """Update status banner on the add exercise screen."""
        # Use red for errors and green for success messages.
        self.status_text = message
        self.status_color = (0.65, 0.16, 0.16, 1) if error else (0.14, 0.4, 0.2, 1)

    def _refresh_records(self) -> None:
        """Reload exercise records and refresh filter state."""
        # Keep browse/add screens in sync with the database.
        self.records = self._load_records()
        self._update_filter_options()
        self.apply_filters()

    def _reset_form(self) -> None:
        """Clear add-exercise form fields and restore defaults."""
        # Reset inputs so a new exercise can be entered cleanly.
        ids = self._add_screen().ids
        ids.name_input.text = ""
        ids.description_input.text = ""
        ids.instructions_input.text = ""
        ids.sets_input.text = ""
        ids.reps_input.text = ""
        ids.time_input.text = ""
        if "default_weight_input" in ids:
            ids.default_weight_input.text = ""
        if self.goal_choice_options:
            self.add_goal_spinner_text = self.goal_choice_options[0]
        if self.muscle_choice_options:
            self.add_muscle_spinner_text = self.muscle_choice_options[0]
        self.add_weight_unit_spinner_text = "kg"
        self.on_add_equipment_change(self._resolve_equipment_choice(""))
        self.rating_spinner_text = "5"
        self.icon_choice_spinner_text = self._no_icon_label
        self.add_icon_source = ""

    def handle_add_exercise(self) -> None:
        """Validate and insert a new exercise into the database."""
        # Enforce required fields and numeric constraints.
        ids = self._add_screen().ids
        name = ids.name_input.text.strip()
        description = ids.description_input.text.strip()
        instructions = ids.instructions_input.text.strip()
        equipment_display = ids.equipment_add_spinner.text.strip() or self._localize_equipment_label("Bodyweight")
        goal_label = ids.goal_add_spinner.text
        goal = self._goal_label_map.get(goal_label)
        muscle_display = ids.muscle_add_spinner.text.strip()
        icon_choice = ""
        if "icon_spinner" in ids:
            icon_choice = ids.icon_spinner.text.strip()
        icon = "" if icon_choice in {"", self._no_icon_label, self._select_icon_label, self._no_icons_label} else icon_choice
        equipment_key = self._equipment_display_to_key.get(equipment_display, "Bodyweight")
        muscle_key = self._muscle_display_to_key.get(muscle_display, muscle_display)

        if not (name and description and instructions and muscle_display and goal and equipment_display):
            self._set_status(
                self._t(
                    "Name, description, execution directions, muscle group, equipment, and goal are required."
                ),
                error=True,
            )
            return

        if muscle_display not in self.muscle_choice_options:
            self._set_status(self._t("Choose a muscle group from the known list."), error=True)
            return

        if equipment_display not in self.equipment_choice_options:
            self._set_status(self._t("Choose equipment from the known list."), error=True)
            return

        if any(r["name"].lower() == name.lower() for r in self.records):
            self._set_status(self._t("Exercise name already exists. Choose another name."), error=True)
            return

        try:
            rating = int(ids.rating_spinner.text)
            if rating < 1 or rating > 10:
                raise ValueError
        except ValueError:
            self._set_status(self._t("Rating must be 1-10."), error=True)
            return

        try:
            sets = self._parse_optional_int(ids.sets_input.text)
            reps = self._parse_optional_int(ids.reps_input.text)
            time_seconds = self._parse_optional_int(ids.time_input.text)
        except ValueError as exc:
            self._set_status(str(exc), error=True)
            return

        supports_weight = self.add_supports_weight
        default_weight_value = None
        default_weight_unit = "kg" if supports_weight else None
        if supports_weight and "default_weight_input" in ids:
            try:
                default_weight_value = self._parse_optional_float(ids.default_weight_input.text)
            except ValueError as exc:
                self._set_status(self._t("Default weight: {error}", error=exc), error=True)
                return
            if "default_weight_unit_spinner" in ids:
                default_weight_unit = "kg"

        try:
            exercise_database.add_exercise(
                name=name,
                short_description=description,
                execution_instructions=instructions,
                required_equipment=equipment_key,
                target_muscle_group=muscle_key,
                goal=goal,
                suitability_rating=rating,
                recommended_sets=sets,
                recommended_reps_per_set=reps,
                recommended_time_seconds=time_seconds,
                supports_weight=supports_weight,
                default_weight_value=default_weight_value,
                default_weight_unit=default_weight_unit,
                icon=icon,
            )
        except sqlite3.IntegrityError:
            self._set_status(self._t("Exercise name already exists. Choose another name."), error=True)
            return
        except sqlite3.DatabaseError as exc:
            self._set_status(self._t("Database error: {error}", error=exc), error=True)
            return

        self._set_status(self._t("Exercise added."))
        self._refresh_records()
        self._reset_form()

    def go_home(self) -> None:
        """Navigate to the home screen after user validation."""
        # Require a current user to access app content.
        if not self._require_user():
            return
        self.ids.screen_manager.current = "home"

    def go_browse(self) -> None:
        """Navigate to the browse screen after user validation."""
        # Require a current user to access app content.
        if not self._require_user():
            return
        self.ids.screen_manager.current = "browse"

    def go_add(self) -> None:
        """Navigate to the add exercise screen after user validation."""
        # Preselect a goal for the add form.
        if not self._require_user():
            return
        if self.goal_choice_options:
            self.add_goal_spinner_text = self._preferred_goal_label()
        self.on_add_equipment_change(self._resolve_equipment_choice(self.add_equipment_spinner_text))
        self.ids.screen_manager.current = "add"

    def go_register(self) -> None:
        """Navigate to the register screen and reset inputs."""
        # Clear previous form values before showing the screen.
        try:
            ids = self._register_screen().ids
        except Exception:
            ids = None
        if ids:
            if "register_username_input" in ids:
                ids.register_username_input.text = ""
            if "register_display_input" in ids:
                ids.register_display_input.text = ""
        preferred = self._preferred_goal_label()
        if preferred and preferred in self.user_goal_options:
            self.register_goal_spinner_text = preferred
        else:
            self.register_goal_spinner_text = self._no_goal_label
        self._set_register_status("")
        self.ids.screen_manager.current = "register"

    def go_users(self) -> None:
        """Navigate to the user selection screen."""
        # No validation needed to view user options.
        self.ids.screen_manager.current = "user"

    def go_history(self) -> None:
        """Navigate to the history screen after user validation."""
        # Refresh history data on entry.
        if not self._require_user():
            return
        self.ids.screen_manager.current = "history"
        self._prefill_workout_date()
        self._load_history()

    def go_recommend(self) -> None:
        """Navigate to the recommendation screen after user validation."""
        # Keep spinners and lists in sync with stored state.
        if not self._require_user():
            return
        self.ids.screen_manager.current = "recommend"
        if not self.rec_goal_spinner_text and self.goal_choice_options:
            self.rec_goal_spinner_text = self.goal_choice_options[0]
        try:
            rec_screen = self._recommend_screen()
            rec_screen.ids.rec_goal_spinner.text = self.rec_goal_spinner_text or ""
            rec_screen.ids.rec_max_time.text = self.rec_max_minutes_text
            rec_screen.ids.rec_list.data = self.rec_recommendations
        except Exception:
            pass
        self._refresh_recommendation_view()

    def _open_confirm_action(self, message: str, confirm_label: str, on_confirm: Callable[[], None]) -> None:
        """Show a confirmation modal before performing a live action."""
        if self._confirm_action_modal is not None:
            try:
                self._confirm_action_modal.dismiss()
            except Exception:
                pass
        self._confirm_action_callback = on_confirm
        modal = ConfirmActionModal(
            message=message,
            confirm_label=confirm_label,
            cancel_label=self._t("Cancel"),
        )
        modal.bind(on_dismiss=lambda *_: self._clear_confirm_action_callback())
        self._confirm_action_modal = modal
        modal.open()

    def prompt_end_live_session(self) -> None:
        """Ask for confirmation before ending the live workout."""
        self._open_confirm_action(
            self._t("End the workout now?"),
            self._t("End workout"),
            lambda: self.end_live_session(early=True),
        )

    def prompt_go_recommend(self) -> None:
        """Ask for confirmation before returning to the plan."""
        self._open_confirm_action(
            self._t("Return to the plan screen?"),
            self._t("Back to plan"),
            self.go_recommend,
        )

    def confirm_action_modal_ok(self) -> None:
        """Run the stored confirmation action if set."""
        callback = self._confirm_action_callback
        self._confirm_action_callback = None
        if callback:
            callback()

    def confirm_action_modal_cancel(self) -> None:
        """Clear the stored confirmation action without running it."""
        self._confirm_action_callback = None

    def _clear_confirm_action_callback(self) -> None:
        """Ensure the stored confirmation action is cleared."""
        self._confirm_action_callback = None

    def go_live(self) -> None:
        """Navigate to the live workout screen if active."""
        # Guard against starting live without a plan.
        if not self.live_active:
            self._set_rec_status(self._t("Start a session from Recommend first."), error=True)
            return
        try:
            self.ids.screen_manager.current = "live"
        except Exception:
            pass

    def go_summary(self) -> None:
        """Navigate to the workout summary screen."""
        # Used after a live session ends.
        try:
            self.ids.screen_manager.current = "summary"
        except Exception:
            pass

    def start_new_session(self) -> None:
        """Reset live state and return to recommendations."""
        # Ensure live state is cleared for a fresh session.
        self.live_active = False
        self.live_paused = False
        self.go_recommend()

    # --- Live mode helpers ---
    def _format_time(self, seconds: float) -> str:
        """Format seconds as a zero-padded MM:SS string."""
        # Clamp negative values to zero before formatting.
        total = int(max(0, round(seconds)))
        minutes, secs = divmod(total, 60)
        return f"{minutes:02d}:{secs:02d}"

    def _current_live_exercise(self) -> Optional[dict[str, Any]]:
        """Return the current live exercise dictionary."""
        # Guard against invalid indices.
        if 0 <= self._live_current_index < len(self.live_exercises):
            return self.live_exercises[self._live_current_index]
        return None

    def _compute_set_target_seconds(self, exercise: Optional[dict[str, Any]]) -> float:
        """Compute a per-set target time based on reps or time."""
        # Use sensible defaults when no guidance is provided.
        if not exercise:
            return 30.0
        time_seconds = exercise.get("time_seconds")
        reps = exercise.get("reps")
        if time_seconds:
            return float(max(10, time_seconds))
        if reps:
            return float(max(20, reps * 4))
        return 30.0

    def _exercise_expected_duration_seconds(self, exercise: Optional[dict[str, Any]]) -> float:
        """Estimate total exercise duration including rest between sets."""
        # Combine per-set targets with rest and any stored estimate.
        if not exercise:
            return 0.0
        sets = exercise.get("sets") or 1
        per_set = self._compute_set_target_seconds(exercise)
        total = sets * per_set
        if sets > 1:
            total += (sets - 1) * float(self.live_rest_seconds)
        est_minutes = exercise.get("estimated_minutes")
        if est_minutes is not None:
            try:
                est_seconds = float(est_minutes) * 60
                total = max(total, est_seconds)
            except (TypeError, ValueError):
                pass
        return max(total, per_set)

    def _set_hint(self, message: str, *, color: tuple = (0.14, 0.4, 0.2, 1), clear_after: float = 3.0) -> None:
        """Display a transient hint message in live mode."""
        # Schedule a clear to avoid stale hints.
        self.live_hint_text = message
        self.live_hint_color = color
        if clear_after > 0:
            Clock.schedule_once(lambda *_: self._clear_hint(message), clear_after)

    def _clear_hint(self, expected: str) -> None:
        """Clear the hint if it matches the expected message."""
        # Avoid wiping newer hints with delayed callbacks.
        if self.live_hint_text == expected:
            self.live_hint_text = ""

    def _flash_signal(self, message: str, color: tuple = (0.16, 0.32, 0.6, 1), duration: float = 2.5) -> None:
        """Show a transient banner for exercise transitions."""
        # Cancel any existing clear event before scheduling a new one.
        self.live_signal_text = message
        self.live_signal_color = color
        if self._signal_clear_event is not None:
            try:
                self._signal_clear_event.cancel()
            except Exception:
                pass
        self._signal_clear_event = Clock.schedule_once(lambda *_: self._clear_signal(message), duration)

    def _clear_signal(self, expected: str) -> None:
        """Clear the live signal banner if it matches the expected text."""
        # Avoid wiping newer banners with delayed callbacks.
        if self.live_signal_text == expected:
            self.live_signal_text = ""
        self._signal_clear_event = None

    def _record_attempt(self, status: str) -> None:
        """Record the current exercise with a completion status once per exercise."""
        # Avoid double-counting attempts within a single exercise.
        if self._live_current_logged:
            return
        exercise = self._current_live_exercise()
        if not exercise:
            return
        normalized_status = "skipped" if status == "skipped" else "completed"
        name = exercise.get("name", "Exercise")
        self._live_attempt_log.append(
            {
                "name": name,
                "status": normalized_status,
                "weight_value": exercise.get("weight_value"),
                "weight_unit": exercise.get("weight_unit"),
            }
        )
        if normalized_status == "skipped":
            self._live_skipped.append(name)
        else:
            self._live_completed.append(name)
        self._live_current_logged = True

    def _update_live_upcoming(self) -> None:
        """Update the list of upcoming exercises."""
        # Compute the remaining exercise names for display.
        upcoming = [
            ex.get("display_name") or self._display_exercise_name(ex.get("name", ""))
            for ex in self.live_exercises[self._live_current_index + 1 :]
        ]
        self.live_upcoming_display = ", ".join(upcoming) if upcoming else self._none_label

    def toggle_live_details(self) -> None:
        """Toggle the live exercise detail expansion."""
        # Flip the detail pane visibility flag.
        self.live_details_expanded = not self.live_details_expanded

    def set_live_rest_seconds(self, value: str) -> None:
        """Allow the user to choose break length while keeping a sane minimum."""
        # Validate input and keep timers in sync when changed mid-session.
        raw = (value or "").strip()
        if not raw:
            self.live_rest_setting_text = str(int(self.live_rest_seconds))
            return
        try:
            seconds = int(raw)
            if seconds < 5:
                raise ValueError
        except ValueError:
            self._set_hint(
                self._t("Break length must be 5 seconds or more."),
                color=(0.65, 0.3, 0.18, 1),
            )
            self.live_rest_setting_text = str(int(self.live_rest_seconds))
            return
        self.live_rest_seconds = seconds
        if self._live_phase in ("rest", "between_exercises"):
            self._live_rest_remaining = float(seconds)
            self.live_rest_timer = self._format_time(self._live_rest_remaining)
        self.live_rest_setting_text = str(seconds)
        self._set_hint(
            self._t("Break length set to {seconds}s.", seconds=seconds),
            color=(0.18, 0.4, 0.2, 1),
        )
        self._update_live_labels()
        self._recalculate_recommendation_times()

    def set_live_weight_value(self, value: str) -> None:
        """Update the current live exercise weight value."""
        # Store parsed values on the active exercise dictionary.
        exercise = self._current_live_exercise()
        if not exercise or not exercise.get("supports_weight"):
            return
        raw = (value or "").strip()
        if not raw:
            exercise["weight_value"] = None
            self.live_weight_value_text = ""
            return
        try:
            parsed = float(raw)
            if parsed <= 0:
                raise ValueError
        except ValueError:
            self._set_hint(self._t("Enter a positive weight."), color=(0.65, 0.16, 0.16, 1))
            return
        exercise["weight_value"] = parsed
        self.live_weight_value_text = self._format_weight_value(parsed)
        self._update_live_labels()

    def set_live_weight_unit(self, unit: str) -> None:
        """Update the current live exercise weight unit."""
        # Normalize units and store on the active exercise.
        exercise = self._current_live_exercise()
        if not exercise or not exercise.get("supports_weight"):
            return
        exercise["weight_unit"] = "kg"
        self.live_weight_unit_text = "kg"
        self._update_live_labels()

    def start_live_workout(self) -> None:
        """Start the live workout timers and state."""
        # Initialize session timing state and start the clock.
        if not self.live_active or self.live_started:
            return
        self.live_started = True
        self.live_paused = False
        self._live_session_started_at = datetime.now()
        self._set_hint(
            self._t("Session started. Begin your first set!"),
            color=(0.18, 0.4, 0.2, 1),
        )
        self._flash_signal(
            self._t("Set {current} started", current=self._live_current_set),
            color=(0.18, 0.5, 0.25, 1),
        )
        self._update_live_labels()
        self._start_live_clock()

    def _compute_live_progress_ratio(self) -> float:
        """Compute progress ring ratio for the current live phase."""
        # Use negative values so the ring animates clockwise.
        exercise = self._current_live_exercise()
        if not exercise or not self.live_active or not self.live_started:
            return 0.0
        if self._live_phase in ("rest", "between_exercises"):
            total = float(self.live_rest_seconds or 0)
            if total <= 0:
                return 0.0
            elapsed = max(0.0, total - self._live_rest_remaining)
            ratio = elapsed / total
            return -max(0.0, min(1.0, ratio))
        target = float(self._live_set_target_seconds or 0)
        if target <= 0:
            return 0.0
        remaining = max(0.0, target - self._live_set_elapsed)
        ratio = remaining / target
        return -max(0.0, min(1.0, ratio))

    def _update_live_progress(self) -> None:
        """Update the progress ring visuals based on session state."""
        # Map phase to colors and timing display.
        if self.live_active and self.live_started:
            if self._live_phase in ("rest", "between_exercises"):
                self.live_progress_color = (0.78, 0.22, 0.22, 1)
                self.live_progress_timer = self._format_time(self._live_rest_remaining)
            elif self._live_phase == "set":
                self.live_progress_color = (0.18, 0.5, 0.25, 1)
                target = float(self._live_set_target_seconds or 0)
                if target > 0:
                    remaining = max(0.0, target - self._live_set_elapsed)
                    self.live_progress_timer = self._format_time(remaining)
                else:
                    self.live_progress_timer = self._format_time(self._live_set_elapsed)
            else:
                self.live_progress_color = (0.18, 0.4, 0.85, 1)
                self.live_progress_timer = "00:00"
        else:
            self.live_progress_color = (0.18, 0.4, 0.85, 1)
            self.live_progress_timer = "00:00"

        ratio = self._compute_live_progress_ratio()
        try:
            Animation.cancel_all(self, "live_exercise_progress")
        except Exception:
            pass
        if self.live_active and self.live_started:
            Animation(live_exercise_progress=ratio, duration=0.45, t="linear").start(self)
        else:
            self.live_exercise_progress = ratio

    def _update_live_labels(self) -> None:
        """Refresh live mode labels and timers."""
        # Synchronize UI labels with internal live state.
        exercise = self._current_live_exercise()
        total_exercises = len(self.live_exercises)
        if not exercise:
            self.live_progress_display = self._t("No session running")
            self.live_exercise_title = self._t("No exercise running")
            self.live_icon_display = ""
            self.live_icon_source = ""
            self.live_muscle_display = ""
            self.live_equipment_display = ""
            self.live_recommendation_display = ""
            self.live_instruction = ""
            self.live_current_set_display = ""
            self.live_state_display = self._t("Not started")
            self.live_upcoming_display = self._none_label
            self.live_exercise_description = ""
            self.live_exercise_instructions = ""
            self.live_exercise_target_display = "—"
            self.live_set_target_display = "—"
            self.live_reps_display = ""
            self.live_reps_visible = False
            self.live_set_counter_display = ""
            self.live_weight_value_text = ""
            self.live_weight_unit_text = "kg"
            self.live_weight_visible = False
            self.live_exercise_timer = "00:00"
            self.live_set_timer = "00:00"
            self.live_rest_timer = "—"
            self.live_exercise_progress = 0.0
            self.live_progress_timer = "00:00"
            self.live_progress_color = (0.18, 0.4, 0.85, 1)
            return
        total_sets = exercise.get("sets") or 1
        self._live_total_sets = total_sets
        display_name = exercise.get("display_name") or self._display_exercise_name(exercise.get("name", ""))
        self.live_progress_display = self._t(
            "Exercise {current}/{total} – {name}",
            current=self._live_current_index + 1,
            total=total_exercises,
            name=display_name,
        )
        self.live_exercise_title = display_name or self._t("Exercise")
        icon_source = exercise.get("icon_source") or self._resolve_icon_source(
            exercise.get("icon", "") or exercise.get("name", "")
        )
        self.live_icon_source = icon_source
        self.live_icon_display = self._t("No icon available") if not icon_source else ""
        self.live_muscle_display = exercise.get("muscle_group", "")
        self.live_equipment_display = exercise.get("equipment", "")
        self.live_recommendation_display = exercise.get("recommendation", "")
        self.live_exercise_description = exercise.get("description", "")
        self.live_exercise_instructions = exercise.get("execution_instructions", "")
        supports_weight = bool(exercise.get("supports_weight"))
        self.live_weight_visible = supports_weight
        if supports_weight:
            weight_unit = self._normalize_weight_unit(exercise.get("weight_unit", "")) or "kg"
            exercise["weight_unit"] = weight_unit
            self.live_weight_unit_text = weight_unit
            self.live_weight_value_text = self._format_weight_value(exercise.get("weight_value"))
        else:
            self.live_weight_value_text = ""
            self.live_weight_unit_text = "kg"
        expected_seconds = self._exercise_expected_duration_seconds(exercise)
        self.live_exercise_target_display = f"~{self._format_time(expected_seconds)}" if expected_seconds else "—"
        set_target = self._live_set_target_seconds or self._compute_set_target_seconds(exercise)
        self.live_set_target_display = self._format_time(set_target) if set_target else "—"
        reps = exercise.get("reps")
        if reps:
            self.live_reps_display = str(reps)
            self.live_reps_visible = True
        else:
            self.live_reps_display = ""
            self.live_reps_visible = False
        current_set = min(self._live_current_set, total_sets)
        self.live_set_counter_display = f"{current_set}/{total_sets}"
        if self._live_phase == "between_exercises":
            next_name = ""
            if self._live_current_index + 1 < len(self.live_exercises):
                next_exercise = self.live_exercises[self._live_current_index + 1]
                next_name = next_exercise.get("display_name") or self._display_exercise_name(
                    next_exercise.get("name", "")
                )
            self.live_instruction = self._t(
                "Rest, then start {name}",
                name=next_name or self._t("the next exercise"),
            )
            self.live_current_set_display = self._t("Completed {count} set(s).", count=total_sets)
        else:
            self.live_instruction = self._build_instruction(exercise)
            self.live_current_set_display = self._t(
                "Set {current} of {total}",
                current=self._live_current_set,
                total=total_sets,
            )
        if self._live_phase == "rest":
            phase_label = self._t("Resting between sets")
        elif self._live_phase == "between_exercises":
            phase_label = self._t("Resting before next exercise")
        elif self._live_phase == "set":
            phase_label = self._t("In set")
        else:
            phase_label = self._t("Not started")
        if self._live_phase == "between_exercises":
            self.live_state_display = phase_label
        else:
            self.live_state_display = self._t(
                "{phase} (Set {current}/{total})",
                phase=phase_label,
                current=self._live_current_set,
                total=total_sets,
            )
        self.live_exercise_timer = self._format_time(self._live_exercise_elapsed)
        self.live_set_timer = self._format_time(self._live_set_elapsed)
        if self._live_phase in ("rest", "between_exercises"):
            self.live_rest_timer = self._format_time(self._live_rest_remaining)
        else:
            self.live_rest_timer = "—"
        self._update_live_upcoming()
        if self.live_active and not self.live_started:
            self.live_state_display = self._t("Ready to start")
            self.live_instruction = self._t("Press Start to begin.")
            self.live_tempo_hint = ""
        else:
            self._update_tempo_hint()
        self._update_live_progress()

    def _build_instruction(self, exercise: dict[str, Any]) -> str:
        """Build the instruction line for the current set."""
        # Provide context-aware guidance based on reps/time.
        reps = exercise.get("reps")
        time_seconds = exercise.get("time_seconds")
        set_prefix = self._t(
            "Set {current}/{total}: ",
            current=self._live_current_set,
            total=exercise.get("sets") or 1,
        )
        supports_weight = bool(exercise.get("supports_weight"))
        weight_label = self._format_weight_label(
            exercise.get("weight_value"),
            exercise.get("weight_unit"),
            supports_weight=supports_weight,
        )
        weight_suffix = f" @ {weight_label}" if supports_weight and weight_label != "—" else ""
        if reps and time_seconds:
            return self._t(
                "{prefix}Target {reps} reps in ~{seconds}s{weight}",
                prefix=set_prefix,
                reps=reps,
                seconds=time_seconds,
                weight=weight_suffix,
            )
        if reps:
            return self._t(
                "{prefix}Perform {reps} controlled reps{weight}",
                prefix=set_prefix,
                reps=reps,
                weight=weight_suffix,
            )
        if time_seconds:
            return self._t(
                "{prefix}Hold for {seconds} seconds{weight}",
                prefix=set_prefix,
                seconds=time_seconds,
                weight=weight_suffix,
            )
        return self._t(
            "{prefix}Move with control and good form{weight}.",
            prefix=set_prefix,
            weight=weight_suffix,
        )

    def _start_live_clock(self) -> None:
        """Start the periodic live timer tick."""
        # Ensure only one clock event is active.
        self._stop_live_clock()
        self._live_clock = Clock.schedule_interval(self._tick_live, 0.5)

    def _stop_live_clock(self) -> None:
        """Stop the live timer tick if running."""
        # Cancel the Kivy Clock event safely.
        if self._live_clock is not None:
            try:
                self._live_clock.cancel()
            except Exception:
                pass
        self._live_clock = None

    def _begin_live_session(self, exercises: list[dict[str, Any]]) -> None:
        """Initialize state for a new live workout session."""
        # Reset counters and populate the exercise queue.
        self.live_exercises = exercises
        self._live_current_index = 0
        self._live_current_set = 1
        self._live_set_elapsed = 0.0
        self._live_exercise_elapsed = 0.0
        self._live_rest_remaining = 0.0
        self._live_phase = "set"
        self._live_set_target_seconds = self._compute_set_target_seconds(self._current_live_exercise())
        self._live_completed = []
        self._live_skipped = []
        self._live_attempt_log = []
        self._live_goal_label = self.rec_goal_spinner_text or ""
        self._live_total_sets_completed = 0
        self._live_current_logged = False
        self.live_paused = False
        self.live_started = False
        self.live_active = True
        self._live_session_started_at = None
        self.live_details_expanded = False
        self.live_rest_setting_text = str(int(self.live_rest_seconds))
        self._update_live_labels()
        self._set_hint(self._t("Press Start when you're ready."), color=(0.18, 0.4, 0.2, 1))

    def _update_tempo_hint(self) -> None:
        """Update tempo guidance based on phase and progress."""
        # Provide rep pacing or hold timing prompts.
        exercise = self._current_live_exercise()
        if not exercise:
            self.live_tempo_hint = ""
            return
        reps = exercise.get("reps")
        if self._live_phase == "between_exercises":
            self.live_tempo_hint = self._t("Rest up — next exercise will start after the break.")
            return
        if self._live_phase == "rest":
            self.live_tempo_hint = self._t("Rest and breathe. Next set starts soon.")
            return
        if reps:
            duration = self._live_set_target_seconds or max(1, reps * 4)
            per_rep = duration / max(reps, 1)
            expected_rep = min(reps, max(1, int(self._live_set_elapsed // max(per_rep, 1) + 1)))
            self.live_tempo_hint = self._t(
                "You should be at repetition {rep} now.",
                rep=expected_rep,
            )
        else:
            target = int(exercise.get("time_seconds") or self._live_set_target_seconds or 0)
            if target:
                self.live_tempo_hint = self._t(
                    "Hold steady: {elapsed}s of {target}s",
                    elapsed=int(self._live_set_elapsed),
                    target=target,
                )
            else:
                self.live_tempo_hint = self._t("Stay controlled and keep breathing.")

    def _compute_completion_percentage(self, completed: int, total: int) -> float:
        """Return 0-100 completion percentage based on completed vs total planned items."""
        # Clamp to bounds so display remains valid.
        if total <= 0 or completed <= 0:
            return 0.0
        ratio = completed / total
        ratio = min(max(ratio, 0.0), 1.0)
        return round(ratio * 100, 2)

    def _tick_live(self, dt: float) -> None:
        """Advance timers and state for live sessions."""
        # Drive phase transitions and progress updates.
        if not self.live_active or self.live_paused or not self.live_started:
            return
        exercise = self._current_live_exercise()
        if not exercise:
            return
        if self._live_phase in ("rest", "between_exercises"):
            self._live_rest_remaining = max(0.0, self._live_rest_remaining - dt)
            if self._live_phase == "rest":
                self._live_exercise_elapsed += dt
                self.live_exercise_timer = self._format_time(self._live_exercise_elapsed)
            self.live_rest_timer = self._format_time(self._live_rest_remaining)
            if self._live_rest_remaining <= 0:
                if self._live_phase == "between_exercises":
                    self._advance_exercise(skipped=False, record_status=False)
                else:
                    self._start_next_set()
            self._update_live_progress()
            return
        self._live_exercise_elapsed += dt
        self._live_set_elapsed += dt
        self.live_exercise_timer = self._format_time(self._live_exercise_elapsed)
        self.live_set_timer = self._format_time(self._live_set_elapsed)
        self._update_tempo_hint()
        self._update_live_progress()
        if self._live_set_target_seconds and self._live_set_elapsed >= self._live_set_target_seconds:
            self._complete_current_set(auto=True)

    def _start_next_set(self) -> None:
        """Advance to the next set or exercise."""
        # Handle set transitions and rest reset.
        exercise = self._current_live_exercise()
        if not exercise:
            return
        total_sets = exercise.get("sets") or 1
        if self._live_current_set >= total_sets:
            self._advance_exercise()
            return
        self._live_phase = "set"
        self._live_current_set += 1
        self._live_set_elapsed = 0.0
        self._live_rest_remaining = 0.0
        self._live_set_target_seconds = self._compute_set_target_seconds(exercise)
        self.live_current_set_display = self._t(
            "Set {current} of {total}",
            current=self._live_current_set,
            total=total_sets,
        )
        self.live_state_display = self._t("In set")
        self.live_rest_timer = "—"
        self._set_hint(
            self._t("Set {current} started", current=self._live_current_set),
            color=(0.16, 0.32, 0.6, 1),
        )
        self._flash_signal(
            self._t("Rest over — set {current} started", current=self._live_current_set),
            color=(0.18, 0.5, 0.25, 1),
        )
        self._update_tempo_hint()
        self._update_live_labels()

    def _complete_current_set(self, *, auto: bool) -> None:
        """Mark the current set complete and enter rest if needed."""
        # Transition to rest or next exercise based on set count.
        exercise = self._current_live_exercise()
        if not exercise or not self.live_active:
            return
        self._live_total_sets_completed += 1
        total_sets = exercise.get("sets") or 1
        if self._live_current_set >= total_sets:
            self._start_between_exercise_rest(skipped=False)
            return
        self._live_phase = "rest"
        self._live_rest_remaining = float(self.live_rest_seconds)
        self.live_state_display = self._t("Resting")
        self.live_rest_timer = self._format_time(self._live_rest_remaining)
        self._set_hint(
            self._t("Rest now – next set will start automatically."),
            color=(0.18, 0.4, 0.2, 1),
        )
        self._flash_signal(
            self._t("Set {current} complete — rest break", current=self._live_current_set),
            color=(0.85, 0.55, 0.2, 1),
        )
        self._update_tempo_hint()
        self._update_live_labels()

    def _start_between_exercise_rest(self, *, skipped: bool) -> None:
        """Enter rest between exercises and record attempt status."""
        # End session if this was the last exercise.
        if not self.live_active:
            return
        exercise = self._current_live_exercise()
        if not exercise:
            return
        at_last_exercise = self._live_current_index >= len(self.live_exercises) - 1
        status = "skipped" if skipped else "completed"
        self._record_attempt(status)
        if at_last_exercise:
            self._flash_signal(self._t("Last exercise finished."), color=(0.18, 0.5, 0.3, 1))
            self.end_live_session(early=skipped)
            return
        self._live_phase = "between_exercises"
        self._live_rest_remaining = float(self.live_rest_seconds)
        self.live_state_display = self._t("Resting before next exercise")
        self.live_rest_timer = self._format_time(self._live_rest_remaining)
        self._set_hint(
            self._t("Exercise finished. Resting before the next one."),
            color=(0.18, 0.4, 0.2, 1),
        )
        self._flash_signal(self._t("Exercise complete — rest break"), color=(0.85, 0.55, 0.2, 1))
        self._update_tempo_hint()
        self._update_live_labels()

    def _advance_exercise(self, *, skipped: bool = False, record_status: bool = True) -> None:
        """Advance to the next exercise in the session."""
        # Reset per-exercise timers and update guidance.
        if record_status:
            self._record_attempt("skipped" if skipped else "completed")
        if self._live_current_index >= len(self.live_exercises) - 1:
            self.end_live_session(early=skipped)
            return
        self._live_current_index += 1
        self._live_current_logged = False
        self._live_current_set = 1
        self._live_set_elapsed = 0.0
        self._live_exercise_elapsed = 0.0
        self._live_rest_remaining = 0.0
        self._live_phase = "set"
        self._live_set_target_seconds = self._compute_set_target_seconds(self._current_live_exercise())
        self._update_live_labels()
        verb = self._t("Skipped") if skipped else self._t("Next exercise")
        self._set_hint(self._t("{verb}: {name}", verb=verb, name=self.live_exercise_title), color=(0.25, 0.32, 0.65, 1))
        self._flash_signal(self._t("Starting {name}", name=self.live_exercise_title), color=(0.16, 0.32, 0.6, 1))

    def skip_current_exercise(self) -> None:
        """Skip the current exercise and enter rest."""
        # Use the between-exercise rest flow.
        if not self.live_active or not self.live_started:
            return
        self._start_between_exercise_rest(skipped=True)

    def manual_next_exercise(self) -> None:
        """Manually finish the exercise and move to rest."""
        # Use the between-exercise rest flow.
        if not self.live_active or not self.live_started:
            return
        self._start_between_exercise_rest(skipped=False)

    def manual_complete_set(self) -> None:
        """Manually complete the current set."""
        # Ignore if already resting.
        if not self.live_active or not self.live_started or self._live_phase in ("rest", "between_exercises"):
            return
        self._complete_current_set(auto=False)

    def toggle_live_pause(self) -> None:
        """Pause or resume the live timers."""
        # Switch between paused and active states.
        if not self.live_active or not self.live_started:
            return
        self.live_paused = not self.live_paused
        if self.live_paused:
            self.live_state_display = self._t("Paused")
            self._set_hint(self._t("Paused – timers stopped."), color=(0.65, 0.3, 0.18, 1))
        else:
            if self._live_phase == "rest":
                self.live_state_display = self._t("Resting")
            elif self._live_phase == "between_exercises":
                self.live_state_display = self._t("Resting before next exercise")
            else:
                self.live_state_display = self._t("In set")
            self._set_hint(self._t("Resumed."), color=(0.18, 0.4, 0.2, 1))

    def end_live_session(self, *, early: bool = False) -> None:
        """End the live session, summarize, and log results."""
        # Finalize timing, attempts, and UI state.
        if not self.live_active:
            return
        if self._current_live_exercise() and not self._live_current_logged:
            self._record_attempt("skipped" if early else "completed")
        now = datetime.now()
        if self._live_session_started_at:
            duration_seconds = int(max(1, (now - self._live_session_started_at).total_seconds()))
        else:
            duration_seconds = 0
        performed_at = now.isoformat(timespec="seconds")
        self.live_active = False
        self.live_paused = False
        self.live_started = False
        self._live_phase = "idle"
        self._live_rest_remaining = 0.0
        self._stop_live_clock()
        self.live_rest_timer = "—"
        self.live_set_timer = self._format_time(self._live_set_elapsed)
        self.live_exercise_timer = self._format_time(self._live_exercise_elapsed)
        self.live_upcoming_display = self._t("Session ended")
        try:
            Animation.cancel_all(self, "live_exercise_progress")
        except Exception:
            pass
        self.live_exercise_progress = 0.0
        self.live_progress_timer = "00:00"
        self.live_progress_color = (0.18, 0.4, 0.85, 1)
        attempts = self._collect_attempts(mark_unattempted_skipped=early)
        completed_count = sum(1 for att in attempts if att.get("status") == "completed")
        skipped_count = sum(1 for att in attempts if att.get("status") == "skipped")
        status = self._t("Workout finished") if not early else self._t("Workout ended early")
        summary = self._t(
            "{status}. Completed {completed}, skipped {skipped}.",
            status=status,
            completed=completed_count,
            skipped=skipped_count,
        )
        self.live_state_display = status
        self.live_progress_display = summary
        self._set_hint(summary, color=(0.18, 0.4, 0.2, 1), clear_after=0)
        self.live_signal_text = ""
        self._prepare_summary(duration_seconds, performed_at, attempts)
        self._log_live_workout(duration_seconds, performed_at, attempts)
        try:
            self.ids.screen_manager.current = "summary"
        except Exception:
            pass

    def _collect_attempts(self, *, mark_unattempted_skipped: bool) -> list[dict[str, Any]]:
        """
        Return a full attempt list, optionally filling unattempted items as skipped when ending early.
        """
        # Merge logged attempts with inferred skips.
        attempts = list(self._live_attempt_log)
        attempt_counts: dict[str, int] = {}
        for att in attempts:
            name = att.get("name", "Exercise")
            attempt_counts[name] = attempt_counts.get(name, 0) + 1

        new_skips: list[dict[str, str]] = []
        if mark_unattempted_skipped:
            seen_counts: dict[str, int] = {}
            for ex in self.live_exercises:
                name = ex.get("name", "Exercise")
                seen_counts[name] = seen_counts.get(name, 0) + 1
                already_attempted = attempt_counts.get(name, 0)
                # If this occurrence has no matching attempt, mark it as skipped.
                if seen_counts[name] > already_attempted:
                    new_skips.append(
                        {
                            "name": name,
                            "status": "skipped",
                            "weight_value": ex.get("weight_value"),
                            "weight_unit": ex.get("weight_unit"),
                        }
                    )
                    self._live_skipped.append(name)
                    attempt_counts[name] = attempt_counts.get(name, 0) + 1

        if not attempts and not new_skips:
            for ex in self.live_exercises:
                name = ex.get("name", "Exercise")
                new_skips.append(
                    {
                        "name": name,
                        "status": "skipped",
                        "weight_value": ex.get("weight_value"),
                        "weight_unit": ex.get("weight_unit"),
                    }
                )
                self._live_skipped.append(name)

        attempts.extend(new_skips)
        return attempts

    def _prepare_summary(self, duration_seconds: int, performed_at: str, attempts: list[dict[str, Any]]) -> None:
        """Populate summary screen fields after a live session."""
        # Convert attempt data into display-friendly strings.
        self.summary_duration_display = self._format_time(duration_seconds or 0)
        self.summary_sets_display = str(self._live_total_sets_completed)
        completed = [
            self._display_exercise_name(att.get("name", "Exercise"))
            for att in attempts
            if att.get("status") == "completed"
        ]
        skipped = [
            self._display_exercise_name(att.get("name", "Exercise"))
            for att in attempts
            if att.get("status") == "skipped"
        ]
        self.summary_completed_display = ", ".join(completed) if completed else self._none_label
        self.summary_skipped_display = ", ".join(skipped) if skipped else self._none_label
        attempts_lines = []
        for att in attempts:
            status_label = self._t("Completed") if att.get("status") == "completed" else self._t("Skipped")
            weight_label = self._format_weight_label(att.get("weight_value"), att.get("weight_unit"))
            display_name = self._display_exercise_name(att.get("name", self._t("Exercise")))
            if weight_label != "—":
                attempts_lines.append(f"{display_name}: {status_label} ({weight_label})")
            else:
                attempts_lines.append(f"{display_name}: {status_label}")
        self.summary_attempts_display = "\n".join(attempts_lines) if attempts_lines else self._t(
            "No exercises attempted."
        )
        self.summary_goal_display = self._live_goal_label or "—"
        self.summary_performed_at_display = performed_at

    def _log_live_workout(self, duration_seconds: int, performed_at: str, attempts: list[dict[str, Any]]) -> None:
        """Persist live session results to the database."""
        # Reuse the workout logging API with live session details.
        if not self.current_user_id:
            return
        exercise_names = [att.get("name", "Exercise") for att in attempts]
        duration_minutes = int(max(1, (duration_seconds + 59) // 60)) if duration_seconds else 1
        try:
            exercise_database.log_workout(
                user_id=self.current_user_id,
                performed_at=performed_at,
                duration_minutes=duration_minutes,
                exercises=exercise_names,
                goal=self._live_goal_label or "",
                duration_seconds=duration_seconds or duration_minutes * 60,
                total_sets_completed=self._live_total_sets_completed,
                exercise_statuses=[(att.get("name", "Exercise"), att.get("status", "completed")) for att in attempts],
                exercise_weights=[
                    (
                        att.get("name", "Exercise"),
                        att.get("weight_value"),
                        att.get("weight_unit") if att.get("weight_value") is not None else None,
                    )
                    for att in attempts
                ],
            )
        except (ValueError, sqlite3.DatabaseError) as exc:
            self._set_history_status(self._t("Could not log workout: {error}", error=exc), error=True)
            return
        self._set_history_status(self._t("Workout logged from live session."))
        self._load_history()


class ExerciseApp(App):
    """Kivy application entry point."""
    # Initializes database and builds the root widget.
    language = StringProperty(localization.DEFAULT_LANGUAGE)

    def tr(self, text: str, lang: Optional[str] = None, **kwargs: Any) -> str:
        """Translate UI text based on the active language."""
        active = lang or self.language or localization.DEFAULT_LANGUAGE
        return localization.translate(text, active, **kwargs)

    def build(self):
        """Construct the Kivy root widget and load KV rules."""
        # Ensure database schema exists before UI uses it.
        exercise_database.initialize_database()
        Builder.load_string(KV)
        return RootWidget()


if __name__ == "__main__":
    ExerciseApp().run()
