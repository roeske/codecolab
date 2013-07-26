/**
 * Prototype for ReportsPage object. This is the client-side controller
 * for the reports page.
 */
(function() {
    window.ReportsPage = (function() {

        ReportsPage.prototype.dialog_height = 480;
        ReportsPage.prototype.dialog_width = 600;
        ReportsPage.prototype.default_dialog_title = 'Report'; 
        ReportsPage.prototype.section_team_reports = null;
        ReportsPage.prototype.section_create_report = null;
        ReportsPage.prototype.is_team_reports_shown = true;
        ReportsPage.prototype.tab_create_report = null;
        ReportsPage.prototype.tab_team_reports = null;
        ReportsPage.prototype.reports_accordion = null;
        ReportsPage.prototype.report_edit_url = null;
        ReportsPage.prototype.search_form = null;

        function ReportsPage(options) { 
            // Reference outer scope.
            var that = this;

            this.report_edit_url = options.report_edit_url;

            // Reference search:
            this.search_form = require("form#report_search");

            this.search_form.ajaxForm({
                success: function(data) {
                    // remove all previous pagination links, they are not needed
                    // anymore
                    $('.reports_paginator').remove();
                    $('div.reports_accordion').html(data);
                    that.reports_accordion.accordion('destroy');
                    that.setup_accordion(that.reports_accordion, true);
                }
            });

            // Reference sections.
            this.section_create_report = require(".section_create_report"); 
            this.section_team_reports = require(".section_team_reports");
           
            // Reference tabs.
            this.tab_create_report = require("#tab_create_report");
            this.tab_team_reports = require("#tab_team_reports");
            this.reports_accordion = require(".reports_accordion");


            this.setup_accordion(this.reports_accordion, true);


            $('#datepickers').hide();

            var datepicker_options = {
              showOn: 'both',
              buttonImage: '/assets/calendar.gif'
            };
            
            $('#start_date').datepicker(datepicker_options);
            $('#end_date').datepicker(datepicker_options);
              
            $("#select_criteria").select2().change(function(ev) {
                var selection = $(this).val();

                if (selection == 'date_range') {
                    $('#datepickers').show();
                    $('#start_date').prop('disabled', false);
                    $('#end_date').prop('disabled', false);
                    $('#q').hide().prop('disabled', true);
                } else {
                    $('#datepickers').hide();
                    $('#start_date').prop('disabled', true);
                    $('#end_date').prop('disabled', true);
                    var hint = 'Enter ' + $(this).find(':selected').text() + '...';
                    $('#q').show().prop('disabled', false).attr('placeholder', hint);
                }
            });

            $('button').first().css('margin-right', '7px');
            // If the team reports tab is clicked, but the section is not
            // already shown, show it.
            this.tab_team_reports.click(function() {
                if(!that.is_team_reports_shown) {
                    that.show_team_reports();
                }
            });

            // If the create report tab is clicked, but the section is not
            // already shown, show it.
            this.tab_create_report.click(function() {
                if(that.is_team_reports_shown) {
                    that.show_create_report();
                }
            });

            // Make sure initial state reflects what is really shown.
            /*
            if (this.is_team_reports_shown) {
                this.show_team_reports();
            } else {
                this.show_create_report();
            }
            */

            // Keep team reports at window height
            jQuery(window).bind('resize', function() { 
                that.fit_to_window(that.reports_accordion);
            });
            that.fit_to_window(that.reports_accordion);

            this._setup_editable_reports();

            $(".report_tags").each(function(i,elem) {
                setup_tags($(elem)); 
            });
        }

        ReportsPage.prototype._setup_editable_reports = function() {
            var that = this;
            jQuery(".editable_report").each(function(i, value) {
                var report_id = $(value).data('id');
                var url = that.report_edit_url + report_id;


                jQuery(value).editable(url, {
                    type: "textarea",
                    name: "text",
                    event: "click",
                    tooltip: "Click to edit...",
                    cssclass: "jeditable",
                    height: "7em",
                    submit: "save",
                    onblur: "cancel",
                    loadurl: url
                });
            });
        };

        ReportsPage.prototype.fit_to_window = function(view) {
            var window_height = jQuery(window).height();
            console.log(window_height);
            view.height(window_height * 0.80);
        };

        ReportsPage.prototype.show_team_reports = function() {
            this.tab_create_report.removeClass("active");
            this.tab_team_reports.addClass("active");

            this.is_team_reports_shown = true;
            this.section_create_report.hide();
            this.section_team_reports.show();
        };

        ReportsPage.prototype.show_create_report = function() {
            this.tab_create_report.addClass("active");
            this.tab_team_reports.removeClass("active");

            this.is_team_reports_shown = false;
            this.section_create_report.show();
            this.section_team_reports.hide();
        };

        ReportsPage.prototype.setup_accordion = function(elem, is_first) {
            var that = this;


            if (!is_first) {
                elem.accordion('destroy');
            }

            $('.report_header').unbind('click');

            elem.accordion({
                header: '.report_header',
                heightStyle: 'content'
            }).jscroll({ 
                nextSelector: '.reports_paginator',
                callback: function() {
                    that.setup_accordion(elem, false);
                }
            });

            $('.report_header').click(function() {
                elem.jscroll.observe();
            });
        };

        return ReportsPage;
    })();
}).call(this);
