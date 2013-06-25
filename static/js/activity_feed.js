(function() {
    window.ActivityFeed = (function() {

        ActivityFeed.prototype.toggle                   = null;
        ActivityFeed.prototype.toggle_icon_show         = null;
        ActivityFeed.prototype.toggle_icon_hide         = null;
        ActivityFeed.prototype.list                     = null;
        ActivityFeed.prototype.list_container           = null;
        ActivityFeed.prototype.container                = null;
        ActivityFeed.prototype.project_name             = null;
        ActivityFeed.prototype.container_width          = null;
        ActivityFeed.prototype.toggle_width             = null;
        ActivityFeed.prototype.piles                    = null;
        ActivityFeed.prototype.piles_width              = null;
        ActivityFeed.prototype.piles_expanded_width     = null;
        
        function ActivityFeed(options) { 
            // copy parameters
            _.extend(this, options);

            // Reference external scope.
            var that = this;

            // setup toggling
            this.toggle_icon_show.hide();
            this.toggle_icon_hide.show();

            this.container_width = this.container.width() - 1;
            this.toggle_width = this.toggle.width();
            this.piles_width = this.piles.width();
            this.piles_expanded_width = this.container_width - 
                                        this.toggle_width +
                                        this.piles_width;

            this.toggle.click(function() {
                var is_visible = $(this).data('is-visible');
                if (is_visible || is_visible == 'true') {
                    that.hide();
                    is_visible = false;
                } else {
                    that.show();
                    is_visible = true;
                }
                // todo: refactor
                $(this).data('is-visible', is_visible);
            });

            this._connect_activity_links();
        }
      
        ActivityFeed.prototype._connect_activity_links = function() {
            $("a.activity_card").each(function(i, elem) {
                // TODO: Refactor
                var obj = $(elem);
                cc_connect_card_to_modal(obj.text(), this.project_name, 
                                         obj, true);
            });
        };

        ActivityFeed.prototype.reload = function() {
            var url = "/project/" + this.project_name + "/activity";
            $.get(url, function(data) {
                this.list.replaceWith(data);
                this.list = require('#list');
                this._connect_activity_links();
            });
        };

        ActivityFeed.prototype.show = function() {
            this.toggle_icon_show.hide();
            this.toggle_icon_hide.show();
            this.list_container.show();
            this.container.width(this.container_width);
            this.toggle.width('6%');
            this.piles.width(this.piles_width);
        };

        ActivityFeed.prototype.hide = function() {
            this.toggle_icon_show.show();
            this.toggle_icon_hide.hide();
            this.list_container.hide();
            this.container.width(this.toggle_width);
            this.toggle.width("100%");
            this.piles.width(this.piles_expanded_width);
        };

        return ActivityFeed;
    })();

}).call(this);
