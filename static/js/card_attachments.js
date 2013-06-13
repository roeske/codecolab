/**
 * Prototype for CardAttachments object. This allows the user
 * to upload a file directly via Amazon S3 and then attach it to
 * a card. Attachments are then made visible in the card
 * automatically via the save_and_reload() method.
 */
(function() {
    window.CardAttachments = (function() {

        CardAttachments.prototype.project_name      = null;
        CardAttachments.prototype.card_id           = null;
        CardAttachments.prototype.file_input        = null; 
        CardAttachments.prototype.file_input_button = null;
        CardAttachments.prototype.progress_selector = null;
        CardAttachments.prototype.progress          = null;
        CardAttachments.prototype.progress_bar      = null;
        CardAttachments.prototype.progress_text     = null;
        CardAttachments.prototype.card_attachments  = null;

        function CardAttachments(options) { 
            // copy parameters
            _.extend(this, options);

            // Reference external scope.
            var that = this;

            // find progress element references
            this.progress_bar   = require(this.progress.find(".progress-bar"));
            this.progress_text  = require(this.progress.find(".progress-text"));

            // Hide the real file input, but make sure it can still be clicked
            // in all browsers. hide() is out of the question.
//            var wrapper = jQuery('<div/>').css({height:0,width:0,'overflow':'hidden'});
//            var real_file_input = jQuery(this.file_input).wrap(wrapper);
            this.file_input.hide();

            // Connect the file_input_button to click the real file
            // input:
            jQuery(this.file_input_button).click(function() {
                that.file_input.click();
            });

            // register change listener for when user selects file.
            jQuery(this.file_input).change(function() {
                var filename = that.get_filename();
                that.s3_upload(filename);
            });
        }


        CardAttachments.prototype.s3_upload = function(filename) {
            var that = this;

            this.progress.fadeIn();

            var s3upload = new S3Upload({
                file_dom_selector: this.file_input,
                s3_sign_put_url: '/sign_s3_upload/',

                onProgress: function(percent, message) { 
                    that.progress_bar.width(percent + "%");
                    var msg = "Uploading: " + filename + " " + percent + "%";
                    that.progress_text.text(msg);
                },

                onFinishS3Put: function(url) { 
                    console.log("onFinishS3Put: finish: ", url);
                    that.save_and_reload(url, filename);
                    that.progress_bar.width(0);
                },

                onError: function(status) {
                    alert("Error uploading file. Please try again.");
                    that.file_input.val("");
                    that.progress_bar.width(0);
                }

            }, filename);
        };


        CardAttachments.prototype.get_filename = function(file_input) {
            var fullPath = this.file_input.val();

            if (fullPath) {
                var startIndex = (fullPath.indexOf('\\') >= 0 ? 
                    fullPath.lastIndexOf('\\') : fullPath.lastIndexOf('/'));

                var filename = fullPath.substring(startIndex);

                if (filename.indexOf('\\') === 0 || filename.indexOf('/') === 0) {
                    filename = filename.substring(1);
                }

                return filename;
            }

            return "unknown_filename";
        };


        CardAttachments.prototype.save_and_reload = function(url, filename) {
            var api_url = this.project_name + "/cards/" + this.card_id + "/attachments";

            var data = JSON.stringify({url: url, filename: filename});

            var that = this;
            $.ajax({
                type: "POST",
                url: api_url,
                data: data, 
                success: function(data) {
                    that.card_attachments.replaceWith(data);
                    that.progress.fadeOut();
                },
                failure: function(data) {
                    alert("Failed to refresh attachments. Please reload the page.");
                },
                dataType: "html",
                contentType: "application/json;charset=UTF-8"
            });
        };

        return CardAttachments;
    })();

}).call(this);

