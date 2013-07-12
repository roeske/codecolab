String.prototype.endsWith = function(suffix) {
    return this.indexOf(suffix, this.length - suffix.length) !== -1;
}; 
function recalculate_container_width() {
  var total_width = 0;
  $(".pile_container").each(function(i, elem) {
      total_width += $(elem).width();
      var inc = parseInt($(elem).css('margin-left'), 10);
      total_width += inc;
      console.log(inc);
      inc = parseInt($(elem).css('margin-right'), 10);
      total_width += inc;
      console.log(inc);
  });
  total_width += 2;
  console.log("total_width="+total_width);

  // Now set the inner #pile_list width to the total width
  $("#pile_list").width(total_width);
  return total_width;
}

function cc_init_list_controls(selector_prefix) {
  // Async list delete
  $(selector_prefix + " .list_delete").click(function() {
      var list_id = $(this).data('list-id');
    
      // If the list has no cards, it is safe to delete.
      var card_count = $("ul[data-id=" + list_id + "] li").size();
      var confirm_delete_msg = "This will archive all the cards in the list. \
Continue?";

      if (card_count === 0 || confirm(confirm_delete_msg)) {
        delete_list(project_name, list_id, function() {
          $("li[data-id=" +  list_id + "]").remove();
          recalculate_container_width();
        });
      }
  });

  // Handle clicks on 'archive' buttons 
  // -- update server
  // -- remove element from dom on success.
  $(selector_prefix + "a.archive").click(handle_archive_click);

  // Append new cards to the bottom of the pile via AJAX.
  $(selector_prefix + "form.add_card").each(function(i, elem) { 

      var pile_selector = "#" + $(elem).data("pile-id");

      $(elem).ajaxForm({
          success: function(text) {
              // Add the card.
              $(pile_selector).append(text);

              // Scroll to the bottom so the card is visible.
              $(pile_selector).scrollTop($(pile_selector)[0].scrollHeight);

              // Select the newly added card.
              var selector = $(pile_selector + " li.card_item");
              var selector_func = function() { return selector; };

              // Update the order of the cards (there is an ordinal that
              // needs to be set on each card to correctly designate its
              // order, independent of how it is currently rendered)
              var updates = cc_cards_reorder_update_dom(selector_func);

              // Update the above on the server.
              cc_reorder_post("cards", updates);

              // Select newly added card to hook up controls
              selector = pile_selector + " li.card_item:last";
              cc_connect_card(selector);
              
              // Connect the raty widget when adding a new card via ajax.
              var elem = $($(selector).find(".difficulty"));
              cc_connect_raty_score(elem, project_name, elem.data("card-id"));

              // Handle archive clicks on the new card.
              $($(selector).find("a.archive")).click(handle_archive_click);

              // Make the new card border glow a bit when it is first shown.
              var color = "#4DCDFF"; // blue
              var width = "2px";

              var temporary = { 
                  borderTopColor: color, 
                  borderTopWidth: width, 
                  borderLeftColor: color,
                  borderLeftWidth: width,
                  borderRightColor: color,
                  borderRightWidth: width,
                  borderBottomColor: color,
                  borderBottomWidth: width
              };

              var transparent = "rgba(0,0,0,0);";

              var invisible = { 
                  borderTopColor: transparent, 
                  borderLeftColor: transparent,
                  borderRightColor: transparent,
                  borderBottomColor: transparent 
              };

              $(selector).animate(temporary, 'slow', function() {
                  $(selector).animate(invisible, 'slow');
              });

              // Reset the add card textbox after the card is added.
              $("input.add_card").val("");
          } 
      });
  });
}


/** Card editor */
function cc_setup_card_description_editor(project_name, card_id) {
    // Setup pagedown
    var converter = Markdown.getSanitizingConverter();
    var editor = new Markdown.Editor(converter);
    editor.run();

    // This feature makes no sense with the way our project
    // is currently configured
    $("#wmd-image-button").hide();
    
    $("#wmd-preview").click(function() {
        $("a.save").click();
    });

    // Setup toggle preview / save
    $("a.save").click(function() {
      if ($(this).text() == "Edit") {

          $(this).text("Save");
          $("#wmd-preview").hide();
          $("#editor_container").show();
      } else {
          // Post the new content
          var description = $("#wmd-input").val();
          var url = "/project/" + project_name + 
                    "/cards/" + card_id + "/description";
    

          var that = this; 
          $.ajax({
              type: "POST",
              url: url,
              contentType: "application/json;charset=UTF-8",

              // Get the new state each time we submit, to toggle.
              data: JSON.stringify({description: description}),
    
              success: function(data) {
                  console.log(data);
                  // Show edit mode
                  $(that).text("Edit");
                  $("#wmd-preview").show();
                  $("#editor_container").hide();
              }
          });
      }
    });
}


function cc_setup_card(project_name, card_id) {
    cc_setup_card_description_editor(project_name, card_id);
}


/** Project View */
function cc_connect_editables(project_name, modal, card_id) {
    var id = card_id;

    // Edit card title
    var url = "/project/" + project_name + "/cards/edit/" + id;
    $(modal).find(".editable.text").editable(url, {
        name: "text",
        event: "click",
        onblur: "submit",
        tooltip: "Click to edit...",
        cssclass: "jeditable",
        height: "24px",

        callback: function(value, settings) {
            console.log("settings=" + settings);
            console.log("value=" + value);

            cc_activity_reload();

            // Must update the card in the list (not modal) when the modal
            // is changed so they do not come out of sync with each other.
            $("li[data-id=" + card_id + "].card_item").find("p span.text").text(value);

            modal.dialog('option', 'title', value);
        }
    });

    /*
    url = "/project/" + project_name + "/cards/edit/" + id;
    $(elem).find(".editable.description").editable(url, {
        onblur: "submit",
        name: "description",
        event: "click",
        style: "inherit",
        tooltip: "Click to edit...",
        cancel: "Cancel",
        submit: "Save",
        type: "textarea",
        width: "400px",
        height: "100px",
        callback: cc_activity_reload
    });
    */

    cc_connect_raty_score($(modal).find(".editable.difficulty"), project_name,
                                        card_id, true);
}


/** 
 * Connects the difficulty rating widget 'raty'. Will load
 * appropriate score from data-score attribute. Configures JSON 
 * postback against /project/<name>/cards/<id>/score POST API.
 */
function cc_connect_raty_score(elem, project_name, card_id, is_cancellable) {
    // Setup difficulty rating widget.
    elem.raty({
        // Load correct score when document is loaded.
        score: function() { 
            score = $(this).data("score");
            return score;
        },

        click: function(score, evt) {
            console.log("score="+score);
        },

        cancel: is_cancellable,
        cancelHint: "Reset this score.",

        // Specify correct paths to images.
        starHalf:   "/js/raty/img/star-half.png",
        starOn:     "/js/raty/img/star-on.png",
        starOff:    "/js/raty/img/star-off.png",
        cancelOff:  "/js/raty/img/cancel-off.png",
        cancelOn:   "/js/raty/img/cancel-on.png",

        // # of stars to display
        number: 3,
        numberMax: 3,

        hints: ["Easy", "Normal", "Difficult"],

        // Allow the user to update the score on the backend by clicking.
        click: function(score, ev) {
            
            $.ajax({
                type: "POST",

                url: "/project/" + project_name + "/cards/" + card_id + "/score",

                data: JSON.stringify({score: score}),
                
                success: function(data) {
                    console.log(JSON.stringify(data));
                    // Update any other copies of this we have.
                    var selector  = ".minicard.difficulty[data-card-id="+card_id+"]";
                    console.log("sel="+selector);

                     
                    var other = $(selector);
                    other.data("score", score);
                    other.raty("score", score);
                                
                    if (score === null) {
                        other.hide();
                    } else {
                        other.show();
                    }

                    // also show milestone
                    other.closest("div.milestone").show();
                },

                contentType: "application/json;charset=UTF-8"
            });
        }
    });
}


/** 
 * Returns an array of sorted 'sort numbers' found in a target list
 * of elements.
 */
function cc_sort_into_numbers_array(elems) {
    // Iterate the children and obtain the data-number values:
    var sort_numbers = [];
    
    elems.each(function(i, elem) {
        sort_numbers.push($(elem).data("number"));
    });
    
    // Sort the data number values least to greatest.
    var sorted_numbers = sort_numbers.sort(function(a,b) {
        return a - b;
    });

    return sorted_numbers;
}


/** 
 * Updates the DOM after cards are reordered. Returns array of
 * update values appropriate for posting back to the server via
 * cc_cards_reorder_post(updates)
 *
 * @param children -- Function returning the list items that need
 *                    to be updated.
 */
function cc_cards_reorder_update_dom(children) {
    // Now, update the pile id of the card in the database, too.
    var updates = [];

    var sorted_numbers = cc_sort_into_numbers_array(children());

    // Re-iterate the existing children and write the numbers back
    // in order, while pushing updates onto the updates array.
    children().each(function(i, elem) {
        var number = sorted_numbers[i];
        elem = $(elem);
        elem.data("number", number);
        
        updates.push({
            _id: elem.data("id"),
            number: number,
            pile_id: elem.data("pile-id")
        });
    });
  
    return updates;
}


function cc_piles_reorder_update_dom(elems) {
    var sorted_numbers = cc_sort_into_numbers_array(elems);
    var updates = [];

    elems.each(function(i, elem) {
        // Update the 'sort number' in the DOM
        elem = $(elem);
        elem.data("number", sorted_numbers[i]);
        updates.push({
            _id: elem.data("id"),
            number: sorted_numbers[i]
        });
    });

    return updates;
}


/** 
 * Post the updates to the "/<name>/reorder" API 
 */
function cc_reorder_post(name, updates) {
    $.ajax({
        type: "POST",
        url: "/" + name + "/reorder", 
        data: JSON.stringify({updates: updates}),
        
        success: function(data) {
            console.log(JSON.stringify(data));
        },

        contentType: "application/json;charset=UTF-8"
    });
}


/**
 * Post updates to /cards/reorder
 *
 * Expected format: [{ _id : <int>, pile_id: <int>, number: <int>}, ...]
 */
function cc_cards_reorder_post(updates) {
    return cc_reorder_post("cards", updates);
}


/**
 * Post updates to /piles/reorder
 *
 * Expected format: [{ _id : <int>,  number: <int>}, ...]
 */
function cc_piles_reorder_post(updates) {
    return cc_reorder_post("piles", updates);
}


/** 
 * Factory for "sortable" objects. Used to make a card sortable in jQueryUI.
 */
function cc_make_card_sorter(selector) {
    var children = function() { 
        return $(selector + " li.card_item").not("li.ui-sortable-placeholder");
    };

    var that = {
        start: function(e, ui) {
            var placeholder_height = ui.item.height() + 2;
            ui.placeholder.height(placeholder_height);
        },

        delay: 100,
        distance: 10,
        revert: "invalid",
        connectWith: "ul.card_list",
        tolerance: "pointer",
        placeholder: "empty_card",

        receive: function(event, ui) {
            console.log("receive");

            // Update the pile id of the card, because we just
            // dropped it into a pile.
            $(ui.item).data("pile-id", $(this).data("id"));
  
            // Update the values in the DOM to reflect the current
            // state of the cards.
            var updates = cc_cards_reorder_update_dom(children);
            
            // Post those updates back to the server.
            cc_cards_reorder_post(updates);
        },


        stop: function(event, ui) {
            console.log("stop");
           
            // Update the values in the DOM to reflect the current
            // state of the cards.
            var updates = cc_cards_reorder_update_dom(children);
            
            // Post those updates back to the server.
            cc_cards_reorder_post(updates);
        }
    };

    return that;
}


function cc_make_pile_sorter(selector) {
    var that = {
        delay: 100,
        distance: 10,
        revert: "invalid",
        tolerance: "pointer",
        handle : ".handle",

        stop: function(event, ui) {
            // Update the values in the DOM to reflect the current
            // state of the cards.
            var updates = cc_piles_reorder_update_dom($(selector).children());
            console.log(updates);            
            // Post those updates back to the server.
            cc_piles_reorder_post(updates);
        }
    };

    return that;
}

/** 
 * Makes fields clazzed with the 'editable' clazz editable, and submit
 * changes to backend when the user presses 'enter'.
 */
function cc_setup_editable_fields(project_name) {
    var selector = ".editable.pile_title";

    // Make pile names editable
    $(selector).each(function(i, elem) {
        var id = $(elem).attr("data-id");
        $(elem).editable("/project/" + project_name + "/piles/edit/" + id, {
            event: "click",
            style: "inherit",
            onblur: "submit",
            cssclass: 'editable_pile_title',
            width: $(elem).width() + 20 + "px"
        });
    });
}


function cc_connect_milestone_spinner(mommy, card_id) {
    return cc_connect_spinner('milestone', mommy, card_id);
}

function cc_connect_assign_to_spinner(parent_elem, card_id) {
    var form = parent_elem.find('form.assign_to');
    form.find('select').select2().change(function() {
        var assigned_users = $(this).val();

        // Update the card with the newly chosen milestone id.
        $.ajax({
            type: 'POST',
            url: form.attr('action'),
            data: JSON.stringify({ assigned: assigned_users }),
            success: console.log,

            failure: function(data) {
                alert("Failed to update assignment field.");
            },
                
            contentType: "application/json;charset=UTF-8"
        });
    });
}


function cc_connect_spinner(clazz, parent_elem, card_id) {
    var form = parent_elem.find("form." + clazz);

    // Fire this function when the milestone spinner's value is changed.
    parent_elem.find("form." + clazz + " select").change(function() {

        // Find the newly selected element
        var changed = $(this).find("option:selected");

        // Find the element_id of the element
        var element_id = changed.data("id");

        // If the milestone id is negative, that is being used to encode
        // 'None', so use the appropriate value.
        if (element_id < 0) {
            element_id = null;
        }
       
        // Find the label of the element (to update state on DOM)
        var label = changed.text();

        var data = {};
        data[clazz + "_id"] = element_id;

        // Update the card with the newly chosen milestone id.
        $.ajax({
            type: form.attr("method"),
            url: form.attr("action"),
        
            data: JSON.stringify(data),
            
            success: function(data) {
                console.log(JSON.stringify(data));

                // Find the correct card item based on id.
                var target = $("li.card_item[data-id="+card_id+"]");

                
                // Update the text of the label with the new value.
                // If the milestone id is < 0, set it to the empty string.
                if (target !== null) {
                    // Locate the label within that target.
                    var target_label = target.find("." + clazz);

                    if (label == "None" || element_id < 0) {
                        // Clear text.
                        target_label.text("");
                        target_label.hide();
                    } else {
                        // Set text.
                        target_label.text(label);
                        target_label.show();
                    }
                }
            },

            failure: function(data) {
                alert("Failed to change milestone.");
            },
                
            contentType: "application/json;charset=UTF-8"
        });
    });
}


function cc_connect_complete_button(project_name, modal, card_id) {
    // capture clicks on the complete button, which is really a link
    // with modified behavior.
    var btn = modal.find("a.card_complete");
    btn.click(function(event) {
        // Don't perform the default action of following the link.
        event.preventDefault();
        
        var that = this;

        // Instead, post the state to the href of the link.
        $.ajax({
            type: "POST",
            url: $(this).attr("href"),

            // Get the new state each time we submit, to toggle.
            data: JSON.stringify({state: $(that).data("state") == "True" }),
            
            success: function(data) {
                var toggle = $(that);
                var card_item_selector = "li.card_item[data-id="+card_id+"] p span.card";
               
                if (data.state) {
                    // Update the toggle button state
                    toggle.find("div.complete").show();
                    toggle.find("div.incomplete").hide();
                    toggle.data("state", "True");
                    
                    // Update the card item text strikethrough
                    var target = $(card_item_selector);
                    target.html("<strike>" + target.text() + "</strike>");
                } else {
                    // Update the toggle button state
                    toggle.find("div.complete").hide();
                    toggle.find("div.incomplete").show();
                    toggle.data("state", "False");

                    // Update the card item text strikethrough
                    var selector = "li.card_item[data-id=" +card_id+"] p span.card_text";
                    target = $(card_item_selector + " strike");
                    $(card_item_selector).html(target.html());
                }

                cc_activity_reload();
            },

            contentType: "application/json;charset=UTF-8"
        });
    });
}


function cc_on_modal_opened(project_name, card_id) {
    var modal_selector = "#modal_" + + card_id;
    var modal = $(modal_selector);


    cc_connect_editables(project_name, modal, card_id);
    cc_connect_milestone_spinner(modal, card_id);
    cc_connect_assign_to_spinner(modal, card_id);
    cc_connect_complete_button(project_name, modal, card_id);
    cc_setup_card(project_name, card_id);
}

function cc_open_modal(modal_id, options, url, on_load) {
    var modal = $("<div id=" + modal_id + "></div>").load(url, on_load) 
                                                    .dialog(options);
    modal.dialog("open").on('dialogresize', function() {
        cc_resize_card($("#" + modal_id).width());
    });
}

function cc_resize_card(width) {

}

function cc_connect_card_to_modal(title, project_name, elem, is_link) {
    // Create id to later reference modal with.
    var modal_id = "modal_" + $(elem).attr("data-id");
    var card_id = $(elem).attr('data-id');

    var url = "/project/" + project_name + "/cards/" + card_id;

    var options = {
        dialogClass: "card_modal",
/*
        show: {
            effect: "blind",
            duration: 100,
        },

        hide: {
            effect: "blind",
            duration: 100
        },
*/
        close: function() {
            // When the modal dialog is closed, completely remove it from the
            // DOM so that it is reloaded next time with fresh state. 
            $("#" + modal_id).dialog("destroy");
        },

        // We need true, but it's breaking focus on sub-dialogs, so...
        // EDIT: unsure when we ever used a sub-dialog but I'm 
        // pretty sure we aren't doing that now and we're not going
        // to.
        modal: true,
        //modal: false,

        title: title,
        autoOpen: false,

        width: screen.width * 0.4,
        minWidth: screen.width * 0.4,
        height: screen.height * 0.8,
        minHeight: screen.height * 0.8
    };

    var on_load = function() {
        cc_on_modal_opened(project_name, card_id);
    };
    
    if (is_link) {
        $(elem).click(function(ev) {
            ev.preventDefault();
            url = $(elem).attr("href");
            console.log("url="+url);
            cc_open_modal(modal_id, options, url, on_load);
        });
    } else {
        $(elem).dblclick(function(ev) {
            cc_open_modal(modal_id, options, url, on_load);
        });
    }
}


function cc_connect_card(elem) {
    var title = $(elem).data("title");
    $(elem).attr("data-project-name", project_name);
    cc_connect_card_to_modal(title, project_name, elem);
}


function cc_make_list_sortable(selector) {
    var sorter = cc_make_card_sorter(selector);
    var matches = $(selector);
    matches.sortable(sorter);//.disableSelection();
}


/** Sets up all state of the project page. */
function cc_project_init(project_name, pile_ids) {
    // Iterate pile ids and make sortable + droppable.
    for (var key in pile_ids) {
        cc_make_list_sortable("#" + pile_ids[key]);
    }
    
    cc_initialize_cards("");
    cc_initialize_lists();
}

function cc_initialize_cards(selector_prefix) {
    $(selector_prefix + "li.card_item").each(function(i, elem) {
        cc_connect_card(elem);
    });
}

function cc_initialize_lists() {
    var pile_selector = "ul#pile_list";
    $(pile_selector).sortable(cc_make_pile_sorter("ul#pile_list"));
    $("ul.card_item, li.card_item").disableSelection();
    cc_setup_editable_fields(project_name);
}
