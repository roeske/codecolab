String.prototype.endsWith = function(suffix) {
    return this.indexOf(suffix, this.length - suffix.length) !== -1;
}; 

String.prototype.htmlDecode = function() {
    var e = document.createElement('div');
    e.innerHTML = this;
    return e.childNodes.length === 0 ? "" : e.childNodes[0].nodeValue;
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

function cc_add_card(socket, project_id, html, pile_id, is_reaction) {
  var pile_selector = "#" + pile_id;
  
  // Add the card.
  $(pile_selector).append(html);

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
  cc_reorder_post(socket, project_id, "cards", updates);

  // Select newly added card to hook up controls
  selector = pile_selector + " li.card_item:last";
  cc_connect_card(selector);
  
  // Connect the raty widget when adding a new card via ajax.
  var elem = $($(selector).find(".difficulty"));
  cc_connect_raty_score(elem, project_name, elem.data("card-id"));

  // Handle archive clicks on the new card.
  $($(selector).find("a.archive")).click(
    make_archive_click_handler(project_id, socket));

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

function cc_init_list_controls(socket, project_id, selector_prefix) {
  // Async list delete
  $(selector_prefix + " .list_delete").click(function() {
      var list_id = $(this).data('list-id');
    
      // If the list has no cards, it is safe to delete.
      var card_count = $("ul[data-id=" + list_id + "] li").size();
      var confirm_delete_msg = "This will archive all the cards in the list. Continue?";

      if (card_count === 0 || confirm(confirm_delete_msg)) {
        delete_list(project_name, list_id, function() {
          $("li[data-id=" +  list_id + "]").remove();
          recalculate_container_width();
          socket.emit("delete_pile", { project_id: project_id,
                                      pile_id: list_id });
        });
      }
  });

  // Handle clicks on 'archive' buttons 
  // -- update server
  // -- remove element from dom on success.
  $(selector_prefix + "a.archive").click(
      make_archive_click_handler(project_id, socket));

  // Append new cards to the bottom of the pile via AJAX.
  $(selector_prefix + "form.add_card").each(function(i, elem) { 

      $(elem).ajaxForm({
          success: function(text) {
              var pile_id = $(elem).data("pile-id");
              socket.emit('add_card', { project_id: project_id, 
                                        pile_id: pile_id, html: text });
              cc_add_card(socket, project_id, text, pile_id, false);
              cc_activity_reload();
          } 
      });
  });
}


/** Card editor */
function cc_setup_card_description_editor(project_name, card_id) {
    // Setup pagedown
    var converter = Markdown.getSanitizingConverter();
    converter.hooks.chain("postConversion", function(text) {
        if (text.trim() === "") {
            return "No Description.";
        } else {
            return text;
        }
    });

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
          var url = "/p/" + project_name + 
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
    var url = "/p/" + project_name + "/cards/edit/" + id;
    $(modal).find(".editable.text").editable(url, {
        name: "text",
        event: "click",
        onblur: "submit",
        tooltip: "Click to edit...",
        cssclass: "jeditable",
        height: "24px",

        callback: function(value, settings) {
            modal.dialog('option', 'title', value.htmlDecode());

            // Must update the card in the list (not modal) when the modal
            // is changed so they do not come out of sync with each other.
            $("li[data-id=" + card_id + "].card_item").find("p span.text").text(value.htmlDecode());

            cc_activity_reload();
        }
    });

    cc_connect_raty_score($(modal).find(".editable.difficulty"), project_name,
                                        card_id, true);
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
    var updates = {};

    var sorted_numbers = cc_sort_into_numbers_array(children());

    // Re-iterate the existing children and write the numbers back
    // in order, while pushing updates onto the updates array.
    children().each(function(i, elem) {
        var number = sorted_numbers[i];
        elem = $(elem);
        elem.data("number", number);
        
        updates[elem.data("id")] = {
            number: number,
            pile_id: elem.data("pile-id")
        };
    });
  
    return updates;
}


function cc_setup_card_search_form(pile_ids) {
    $('#card_search').ajaxForm({
        success: function(data) {
            // New search, reset all pile containers to be shown.
            $('.pile_container').show();

            // hide cards that are not found in the search results.
            // show cards that are.
            $(".card_item").each(function(i, elem) {
                if (!data[$(elem).data('id')]) {
                    $(elem).hide(); 
                } else {
                    $(elem).show();
                }
            });

            var key;
            if (data['is_locked']) {
                // hide piles which are empty.
                $(".pile_container").each(function(i, elem) {
                    var len = $(elem).find('.card_item:visible').length;
                    console.log("len="+len);
                    if(len === 0) {
                        $(elem).hide();
                    } 
                });
                $(".locked_indicator").show();
                $('input[value="clear"]').show();

                for (key in pile_ids) {
                    $("#" + pile_ids[key]).sortable('disable');
                }
                $('ul#pile_list').sortable('disable');
            } else {
                $(".locked_indicator").hide();
                $('input[value="clear"]').hide();
                for (key in pile_ids) {
                    $("#" + pile_ids[key]).sortable('enable');
                }
                $('ul#pile_list').sortable('enable');
            }

            if (data['is_cleared']) {
                $('input[name="q"]').val("").show().prop('disabled', false).attr('placeholder', 'Enter Search Text...');
                $('#select_criteria').select2("val", "full_text");
                $('input[name="end_date"]').val("").prop('disabled', true);
                $('input[name="start_date"]').val("").prop('disabled', true);
                $('#datepickers').hide();
            }
        }
    });
}


function cc_piles_reorder_update_dom(elems) {
    var sorted_numbers = cc_sort_into_numbers_array(elems);
    var updates = {};

    elems.each(function(i, elem) {
        // Update the 'sort number' in the DOM
        elem = $(elem);
        elem.data("number", sorted_numbers[i]);
        updates[parseInt(elem.data('id'),10)] = {
            number: sorted_numbers[i]
        };
    });

    return updates;
}


/** 
 * Post the updates to the "/<name>/reorder" API 
 */
function cc_reorder_post(socket, project_id, name, updates) {
    $.ajax({
        type: "POST",
        url: "/" + name + "/reorder", 
        data: JSON.stringify({updates: updates, project_id: project_id}),
        
        success: function(data) {
            // If the cards are successfully reordered on the server,
            // push them via socket.io to all other clients connected
            // to this project's hub.
            var ev_name = "reorder_" + name;
            console.log("emitting: " + ev_name);
            socket.emit(ev_name, data); 
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
function cc_cards_reorder_post(socket, project_id, updates) {
    return cc_reorder_post(socket, project_id, "cards", updates);
}


/**
 * Post updates to /piles/reorder
 *
 * Expected format: [{ _id : <int>,  number: <int>}, ...]
 */
function cc_piles_reorder_post(socket, project_id, updates) {
    return cc_reorder_post(socket, project_id, "piles", updates);
}


/** 
 * Factory for "sortable" objects. Used to make a card sortable in jQueryUI.
 */
function cc_make_card_sorter(socket, project_id, selector) {
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
            console.log("REORDER_POST");
            console.log("socket=");console.log(socket);
            cc_cards_reorder_post(socket, project_id, updates);
        },


        stop: function(event, ui) {
            console.log("stop");
           
            // Update the values in the DOM to reflect the current
            // state of the cards.
            var updates = cc_cards_reorder_update_dom(children);
            
            // Post those updates back to the server.
            cc_cards_reorder_post(socket, project_id, updates);
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
        $(elem).editable("/p/" + project_name + "/piles/edit/" + id, {
            event: "click",
            style: "inherit",
            onblur: "submit",
            cssclass: 'editable_pile_title',
            width: $(elem).width() + 20 + "px"
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


function cc_on_modal_opened(project_name, card_id) {
    var modal_selector = "#modal_" + + card_id;
    var modal = $(modal_selector);


    cc_connect_editables(project_name, modal, card_id);
    cc_connect_milestone_spinner(modal, card_id);

    cc_setup_card(project_name, card_id);
}

function cc_open_modal(modal_id, options, url, on_load) {
    var modal = $("<div id=" + modal_id + "></div>").load(url, on_load).dialog(options);

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

    var url = "/p/" + project_name + "/cards/" + card_id;

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

        width: 800, 
        minWidth: 800,
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


function cc_make_list_sortable(socket, project_id, selector) {
    var sorter = cc_make_card_sorter(socket, project_id, selector);
    var matches = $(selector);
    matches.sortable(sorter);
}

var SOCKETIO_SERVER = "http://192.241.181.165:8080"


function cc_insert_card_into_pile(card, number, pile_id) {
    // It's in the wrong pile. Insert it before the
    // first card with a greater ordinal.
    var card_list = $("ul.card_list[data-id=" + pile_id + "] li");
    if (card_list.length > 0) {
        var is_inserted = false;
        card_list.each(function(i, neighbor_elem) {
            var neighbor = $(neighbor_elem);
            var neighbor_number = parseInt(neighbor.data('number'), 10);
            if (neighbor_number > number) {
                neighbor.before(card);
                is_inserted = true;
                return false;
            }
        });

        // this is the case where it's inserted at the end of the list
        if (!is_inserted) {
            $("ul.card_list[data-id=" + pile_id + "]").append(card);
        }
    } else {
        $("ul.card_list[data-id=" + pile_id + "]").append(card);
    }
}



/** Sets up all state of the project page. */
function cc_project_init(socket, project_id, pile_ids) {
    // Iterate pile ids and make sortable + droppable.
    for (var key in pile_ids) {
        cc_make_list_sortable(socket, project_id, "#" + pile_ids[key]);
    }
   
    cc_initialize_cards("");
    cc_initialize_lists(socket, project_id);
    cc_setup_card_search_form(pile_ids);
}

function cc_initialize_cards(selector_prefix) {
    $(selector_prefix + "li.card_item").each(function(i, elem) {
        cc_connect_card(elem);
    });
}

function cc_initialize_lists(socket, project_id) {
    var pile_selector = "ul#pile_list";
    $("#__piles_container").sortable(cc_make_pile_sorter(socket, project_id,
        "ul#pile_list"));
    $("ul.card_item, li.card_item").disableSelection();
    cc_setup_editable_fields(project_name);
}


function cc_append_pile(project_id, data, socket) {
      $("ul#pile_list").append(data); 
      var new_pile = $("ul#pile_list > li > ul").last(); 
      var width = recalculate_container_width();
      cc_init_list_controls(socket,  project_id, "#pile_" + new_pile.data("id") + " ");
      cc_initialize_lists();
      console.log("new_pile...");
      console.log(new_pile);
      cc_initialize_cards("#" + new_pile.attr("id") + " > ");
      cc_make_list_sortable($("ul#pile_list > li > ul.card_list").last());
      // finally, scroll the piles div all the way to the right so it 
      // can be seen
      $("div#piles").animate({ scrollLeft: width });
      $('#add_list_form input[type="text"]').val("");
}

function ajax_toggle(that, callback) {
    that = $(that);

    $.ajax({
        type: "GET",
        url: that.attr("href"),
        
        success: function(data) {
            if (data.state === true) {
                that.find(".true").show();
                that.find(".false").hide();
            } else {
                that.find(".true").hide();
                that.find(".false").show();
            }
        
            console.log(data);

            if (callback !== undefined) {
                callback(data);
            }
        },

        contentType: "application/json;charset=UTF-8"
    });
}

function toggle_button_handler() {
    ajax_toggle(this);
    return false;
}
