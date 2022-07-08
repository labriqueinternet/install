let YUNOHOSTDOMAINS = [".noho.st",".ynh.fr",".nohost.me"]

$(document).ready(function() {

    if (window.location.pathname != "/install") {
        window.location.replace(window.location.origin + "/install");
    };

    $("#completed-1").hide();
    $("#completed-2").hide();

    function steps_update_view()
    {
        $.getJSON(window.location + "/status")
            .done(function(data) {

                steps = data["steps"];
                steps_update_progress_bar(steps);
                steps.forEach(function (step_data) { steps_update_list(step_data); });
                failure = false;
                steps.forEach(function (step_data) { if (step_data.status == "failed") { failure = true; } });
                completed = true;
                steps.forEach(function (step_data) { if ((step_data.status != "success") && (step_data.status != "skipped")) { completed = false; } });

                inactive = (! data["active"]) && (! completed);

                $(".progress-bar").removeClass("progress-bar-striped").removeClass("progress-bar-animated").removeClass("bg-warning").removeClass("bg-danger").removeClass("bg-success");

                if (failure) {
                    $(".progress-bar").addClass("bg-danger");
                }
                else if (inactive) {
                    $(".progress-bar").addClass("bg-warning");
                    $("#steps .fa.fa-cog").removeClass("fa-cog").removeClass("fa-spin").addClass("fa-stop");
                }
                else if (completed) {
                    $(".progress-bar").addClass("bg-success");
                }
                else {
                    $(".progress-bar").addClass("progress-bar-striped").addClass("progress-bar-animated");
                }

                if (failure || inactive) {
                    $("#retry").show();
                    $("#fullreset").show();
                    $("#retry").removeClass("disabled");
                    $("#fullreset").removeClass("disabled");
                    if (inactive) { setTimeout(steps_update_view, 5000); } 
                }
                else if (completed) {
                    $("#steps").hide();
                    $("#footer").hide();
                    $("#completed-1").show();
                    setTimeout(function () { $("#progress").hide(); $("#completed-1").hide(); $("#completed-2").show(); }, 5000);
                }
                else {
                    $("#retry").hide();
                    $("#fullreset").hide();
                    setTimeout(steps_update_view, 2000);
                }
            })
            .fail(function() {
                $("#steps .fa.fa-cog").removeClass("fa-cog").removeClass("fa-spin").addClass("fa-question");
                setTimeout(steps_update_view, 2000);
            });
    };

    var steps_update_debug_timer;
    function steps_update_debug()
    {
        $.getJSON(window.location + "/debug")
            .done(function(steps) {
                steps.forEach(function (step_data) {
                    step = $("#step-"+step_data.id)[0];
                    if (! step_data.logs.length)
                    {
                        $(".debug", step).hide();
                        return
                    }
                    $(".debug", step).show().html(
                        step_data.logs
                        .replace(/ ERROR /g,   function (match) { return '<span class="text-danger">' +match+'</span>'})
                        .replace(/ WARNING /g, function (match) { return '<span class="text-warning">'+match+'</span>'})
                        .replace(/ INFO /g,    function (match) { return '<span class="text-info">'   +match+'</span>'})
                        .replace(/ SUCCESS /g, function (match) { return '<span class="text-success">'+match+'</span>'})
                        .replace(/ DEBUG /g,   function (match) { return '<span class="text-muted">'  +match+'</span>'})
                    );
                });
            })
            .always(function() {
                if ($("#debug_mode")[0].checked)
                {
                    steps_update_debug_timer = setTimeout(steps_update_debug, 5000);
                }
            })
    };

    function steps_toggle_debug_mode()
    {
        if ($("#debug_mode")[0].checked)
        {
            steps_update_debug();
            $("#install_status > div").addClass("col-12").removeClass("col-lg-6").removeClass("col-md-8");
        }
        else
        {
            clearTimeout(steps_update_debug_timer);
            $("#install_status > div").removeClass("col-12").addClass("col-lg-6").addClass("col-md-8");
            $(".debug").hide();
        }
    };

    function steps_update_progress_bar(steps)
    {
        count = 0;
        steps.forEach(function (step_data) {
            if ((step_data.status == "success") || (step_data.status == "skipped"))
            {
                count += 1;
            }
            else if (step_data.status == "ongoing")
            {
                count += 0.5;
            }
        });

        percent = 100 * count / steps.length;
        $("#progress .progress-bar").css('width', percent+'%').attr('aria-valuenow', percent);
    };

    function steps_update_list(step_data)
    {
        step = $("#step-"+step_data.id)[0];
        status_to_icon = {
            pending: "",
            success: "fa-check-circle text-success",
            ongoing: "fa-cog fa-spin",
            failed: "fa-times-circle text-danger",
            skipped: "fa-times text-muted",
        };

        $(".step-icon", step)[0].classList = "step-icon fa fa-fw " + status_to_icon[step_data.status];
        if ((step_data.status == "pending") || (step_data.status == "skipped"))
        {
            $("h5", step).addClass("text-muted");
        }
        else
        {
            $("h5", step).removeClass("text-muted");
        }

        if (((step_data.status != "ongoing") && (step_data.status != "failed")) || (! step_data.message))
        {
            $(".step-info", step).hide();
        }
        else
        {
            $(".step-info", step).show().html(step_data.message);
        }
    };

    // #####################################################
    // #####################################################
    // #####################################################

    function form_update_cube_file_input()
    {
        var fileInput = $('input[id="cubefile"]');
        var fileLabel = $('label[for="cubefile"].custom-file-label');
        var file = fileInput[0].files[0];
        var fileReader = new FileReader();

        fileLabel.html(file.name);
        fileInput.removeClass("is-valid").removeClass("is-invalid");

        fileReader.readAsText(file);
        fileReader.onload = function(e)
        {
            raw = e.target.result;
            fileInput.attr("content", e.target.result);
            form_validate_item(fileInput);
        };
        fileReader.onerror = function(e)
        {
            console.log(e);
        };
    };

	function form_update_subscribe(){
		var yunohost = false;
		for (let i in YUNOHOSTDOMAINS){
			if ($("#main_domain").val().endsWith(YUNOHOSTDOMAINS[i])){
				yunohost = true;
			}
		}
		var body = $(".subscribe-password-div")
		if (yunohost){
			body.show();
            $("input", body).addClass("validate");
		} else {
			body.hide();
			$("#domain_password").val("");
			$("#domain_password_repeat").val("");
            $("input", body).removeClass("validate");
		}
	}
	
    function form_update_optional_section(name)
    {
        status_ = $("#enable_" + name)[0].checked;
        body = $("#"+name+" .collapse");
        if (status_)
        {
            body.collapse("show");
            $("input", body).addClass("validate");
        }
        else
        {
            body.collapse("hide");
            $("input", body).removeClass("validate");
        }
    };

    function form_validate_item_custom(item)
    {
        id = item.prop("id");
        if (id == "cubefile")
        {
            try
            {
                JSON.parse(item.attr("content"));
            }
            catch(e)
            {
                console.log(e);
                return "invalidjson"
            }
            return true;
        }
        else if (id == "password_repeat")
        {
            if (item.val() !== $("input[id='password']").val())
            {
                return "nomatch";
            }
            return true;
        }
        else if (id == "wifi_password_repeat")
        {
            if (item.val() !== $("input[id='wifi_password']").val())
            {
                return "nomatch";
            }
            return true;
        }
        else if (id == "domain_password_repeat")
        {
            if (item.val() !== $("input[id='domain_password']").val())
            {
                return "nomatch";
            }
            return true;
        }
    };

    function form_validate_item(item)
    {
        var isValid = true;
        item.removeClass("is-valid").removeClass("is-invalid");
        item.siblings(".invalid-feedback").hide();
        item.siblings(".invalid-feedback.default").css("display", "");
        if (item.val() != "" && item.prop("validity").valid)
        {
            if (typeof item.attr("custom-validation") !== "undefined")
            {
                var result = form_validate_item_custom(item);
                if (result !== true)
                {
                    item.siblings(".invalid-feedback").hide();
                    item.siblings(".invalid-feedback."+result).css("display", "");
                    item.addClass("is-invalid");
                    return false;
                }
            }

            item.addClass("is-valid");
            return true;
        }
        else
        {
            item.addClass("is-invalid");
            return false;
        }
    };

    function form_validate()
    {
        var form = $("#install_form");
        var isValid = true;
        $(".validate", form).each(function() {
            isValid = form_validate_item($(this)) && isValid;
        });
        return isValid;
    };


    if ($("#install_form").length)
    {

        $("#enable_vpn")[0].checked = true;
        $("#enable_wifi")[0].checked = true;

        $("#enable_vpn").click(function() {  form_update_optional_section("vpn") });
        $("#enable_wifi").click(function() { form_update_optional_section("wifi") });

        form_update_optional_section("vpn");
        form_update_optional_section("wifi");

        $(".invalid-feedback").hide();
        $(".invalid-feedback.default").css("display", "");

		$("#main_domain").on("change",form_update_subscribe)
		form_update_subscribe()

        cube_input = $("input[id='cubefile']");
        cube_input.change(form_update_cube_file_input);
        if (cube_input.val())
        {
            form_update_cube_file_input();
        }

        $(".validate", $("#install_form")).on('change', function() {
            return form_validate_item($(this));
        });

        $("#install_form").submit(function(e) {
            $("#submit_error").hide();
            $("#install_form button[type='submit']").prop("disabled", true);
            e.preventDefault();
            if (!form_validate())
            {
                $("#install_form button[type='submit']").prop("disabled", false);
                return false;
            }

            serialized_form = {};
            $("input").each(function(i, item) {
                serialized_form[$(item).attr("name")] = $(item).val();
            });
            serialized_form.cubefile = null;

            serialized_form.enable_vpn = $("#enable_vpn")[0].checked;
            serialized_form.enable_wifi = $("#enable_wifi")[0].checked;
            if (serialized_form.enable_vpn)
            {
                serialized_form.cubefile = $('input[id="cubefile"]').attr("content");
            }

            var xhr = $.post(window.location + "/", serialized_form);
            xhr.done(function (data) {
                window.location.reload();
            })
            xhr.fail(function (data) {
                $("#submit_error").html(data.responseText).show();
            })
            xhr.always(function () {
                $("#install_form button[type='submit']").prop("disabled", false);
            })
        });
    }

    if ($("#install_status").length)
    {
        $("#retry").hide();
        $("#retry").click(function() {
            $("#retry").addClass("disabled");
            $("#fullreset").addClass("disabled");
            $.post(window.location + "/retry");
            setTimeout(steps_update_view, 2000);
        });

        $("#fullreset").hide();
        $("#fullreset-wait").hide();
        $("#fullreset").click(function() {
            $("#retry").addClass("disabled");
            $("#fullreset").addClass("disabled");
            $("#fullreset .fa").addClass("fa-spin");
            $("#fullreset-wait").show();
            xhr = $.post(window.location + "/fullreset");
            xhr.always(function () {
                window.location.reload();
            });
        });

        $("#debug_mode")[0].checked = false;
        $("#debug_mode").click(function() { steps_toggle_debug_mode() });
        steps_update_view();
    }
});
