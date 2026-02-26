function OnInit()
{
	$("#vendorFilterBtn").on("click", function(){
		$("#VendorFilterList").slideToggle(300);
		$(this).find(".CArrow").toggleClass("active");
	});

	TranslatePage();

	RequestProfile();
}


function RequestProfile()
{
	var tSend={};
	tSend['sequence_id']=Math.round(new Date() / 1000);
	tSend['command']="request_userguide_profile";

	SendWXMessage( JSON.stringify(tSend) );
}

function HandleStudio( pVal )
{
	let strCmd=pVal['command'];

	if(strCmd=='response_userguide_profile')
	{
		HandleModelList(pVal['response']);
	}
}

function ShowPrinterThumb(pItem, strImg)
{
	$(pItem).attr('src',strImg);
	$(pItem).attr('onerror',null);
}

function HandleModelList( pVal )
{
	if( !pVal.hasOwnProperty("model") )
		return;

    pModel=pVal['model'];

	let nTotal=pModel.length;
	let ModelHtml={};
	for(let n=0;n<nTotal;n++)
	{
		let OneModel=pModel[n];

		let strVendor=OneModel['vendor'];

		//Add Vendor section in PrinterGrid
		if($(".OneVendorBlock[vendor='"+strVendor+"']").length==0)
		{
			let sVV=strVendor;
			if( sVV=="BBL" )
				sVV="Bambu Lab";
			if( sVV=="Custom")
				sVV="Custom Printer";
			if( sVV=="Other")
				sVV="Orca colosseum";

			let HtmlNewVendor='<div class="OneVendorBlock" vendor="'+strVendor+'">'+
'<div class="BlockBanner">'+
'	<div class="BannerBtns">'+
'		<div class="SmallBtn_Green trans" tid="t11" onClick="SelectPrinterAll('+"\'"+strVendor+"\'"+')">all</div>'+
'		<div class="SmallBtn trans" tid="t12" onClick="SelectPrinterNone('+"\'"+strVendor+"\'"+')">none</div>'+
'	</div>'+
'	<a>'+sVV+'</a>'+
'</div>'+
'<div class="PrinterArea">'+
'</div>'+
'</div>';

			$('#PrinterGrid').append(HtmlNewVendor);

			// Add corresponding vendor checkbox to left filter panel
			let HtmlVendorFilter='<div class="checkboxText"><input class="inputIndent" type="checkbox" vendorfilter="'+strVendor+'" onChange="VendorFilterClick()" />'+sVV+'</div>';
			$('#VendorFilterList').append(HtmlVendorFilter);
		}

		//Collect Html Node Nozzle Html
		if( !ModelHtml.hasOwnProperty(strVendor))
			ModelHtml[strVendor]='';

		let NozzleArray=OneModel['nozzle_diameter'].split(';');
		let HtmlNozzel='';
		for(let m=0;m<NozzleArray.length;m++)
		{
			let nNozzel=NozzleArray[m];
			HtmlNozzel += '<label class="pNozzel TextS2"><input type="checkbox" model="' + OneModel['model'] + '" nozzel="' + nNozzel + '" vendor="' + strVendor +'" onclick="CheckBoxOnclick(this)" /><span>'+nNozzel+'</span><span class="trans" tid="t13">mm nozzle</span></label>';
		}

		let CoverImage=OneModel['cover'];
		ModelHtml[strVendor]+='<div class="PrinterBlock">'+
'	<div class="PImg"><img src="'+CoverImage+'"  /></div>'+
'    <div class="PName">'+OneModel['name']+'</div>'+ HtmlNozzel +'</div>';
	}

	//Update Nozzle Html Append
	for( let key in ModelHtml )
	{
		$(".OneVendorBlock[vendor='"+key+"'] .PrinterArea").append( ModelHtml[key] );
	}

	// Check all vendors in left filter
	$('#VendorFilterList input').prop("checked", true);
	$('#VendorAll').prop("checked", true);

	//Update Checkbox state
	$('input[type=checkbox][model]').prop("checked", false);
	for(let m=0;m<nTotal;m++)
	{
		let OneModel=pModel[m];

		let SelectList=OneModel['nozzle_selected'];
		if(SelectList!='')
		{
			SelectList=OneModel['nozzle_selected'].split(';');
    		let nLen=SelectList.length;

		    for(let a=0;a<nLen;a++)
			{
			    let nNozzel=SelectList[a];
				$("input[vendor='" + OneModel['vendor'] + "'][model='" + OneModel['model'] + "'][nozzel='" + nNozzel + "']").prop("checked", true);

				SetModelSelect(OneModel['vendor'], OneModel['model'], nNozzel, true);
			}
		}
		else
		{
			$("input[vendor='"+OneModel['vendor']+"'][model='"+OneModel['model']+"']").prop("checked", false);
		}
	}

	TranslatePage();
}

function ChooseAllVendor()
{
	let bCheck=$('#VendorAll').prop("checked");
	$("#VendorFilterList input").prop("checked", bCheck);

	$(".OneVendorBlock").each(function(){
		if(bCheck)
			$(this).show();
		else
			$(this).hide();
	});
}

function VendorFilterClick()
{
	// Sync "all" checkbox
	let nChecked=$("#VendorFilterList input:not(#VendorAll):checked").length;
	let nAll    =$("#VendorFilterList input:not(#VendorAll)").length;

	if(nAll==nChecked)
		$('#VendorAll').prop("checked",true);
	else
		$('#VendorAll').prop("checked",false);

	// Show/hide vendor sections
	let pVendor=$("#VendorFilterList input:not(#VendorAll)");
	for(let n=0;n<pVendor.length;n++)
	{
		let oneV=pVendor[n];
		let vName=oneV.getAttribute("vendorfilter");
		if(oneV.checked)
			$(".OneVendorBlock[vendor='"+vName+"']").show();
		else
			$(".OneVendorBlock[vendor='"+vName+"']").hide();
	}
}

function CheckBoxOnclick(obj) {
	let strModel = obj.getAttribute("model");
	let strVendor = obj.getAttribute("vendor");
	let strNozzel = obj.getAttribute("nozzel");

	SetModelSelect(strVendor, strModel, strNozzel, obj.checked);
}

function SetModelSelect(vendor, model, nozzel, checked) {
	if (!ModelNozzleSelected.hasOwnProperty(vendor) && !checked) {
		return;
	}

	if (!ModelNozzleSelected.hasOwnProperty(vendor) && checked) {
		ModelNozzleSelected[vendor] = {};
	}

	let oVendor = ModelNozzleSelected[vendor];
	if (!oVendor.hasOwnProperty(model)) {
		oVendor[model] = {};
	}

	let oModel = oVendor[model];
	if (oModel.hasOwnProperty(nozzel) || checked) {
		oVendor[model][nozzel] = checked;
	}
}

function GetModelSelect(vendor, model, nozzel) {
	if (!ModelNozzleSelected.hasOwnProperty(vendor)) {
		return false;
	}

	let oVendor = ModelNozzleSelected[vendor];
	if (!oVendor.hasOwnProperty(model)) {
		return false;
	}

	let oModel = oVendor[model];
	if (!oModel.hasOwnProperty(nozzel)) {
		return false;
	}

	return oVendor[model][nozzel];
}

function FilterModelList(keyword) {

	//Save checkbox state
	let ModelSelect = $('input[type=checkbox][model]');
	for (let n = 0; n < ModelSelect.length; n++) {
		let OneItem = ModelSelect[n];
		SetModelSelect(OneItem.getAttribute("vendor"), OneItem.getAttribute("model"), OneItem.getAttribute("nozzel"), OneItem.checked);
	}

	let nTotal = pModel.length;
	let ModelHtml = {};
	let kwSplit = keyword.toLowerCase().match(/\S+/g) || [];

	$('#PrinterGrid').empty();
	for (let n = 0; n < nTotal; n++) {
		let OneModel = pModel[n];

		let strVendor = OneModel['vendor'];
		let search = (OneModel['name'] + '\0' + strVendor).toLowerCase();

		if (!kwSplit.every(s => search.includes(s)))
			continue;

		//Add Vendor Html Node
		if ($(".OneVendorBlock[vendor='" + strVendor + "']").length == 0) {
			let sVV = strVendor;
			if (sVV == "BBL") sVV = "Bambu Lab";
			if (sVV == "Custom") sVV = "Custom Printer";
			if (sVV == "Other") sVV = "Orca colosseum";

			let HtmlNewVendor = '<div class="OneVendorBlock" vendor="' + strVendor + '">' +
				'<div class="BlockBanner">' +
				'	<div class="BannerBtns">' +
				'		<div class="SmallBtn_Green trans" tid="t11" onClick="SelectPrinterAll(' + "\'" + strVendor + "\'" + ')">all</div>' +
				'		<div class="SmallBtn trans" tid="t12" onClick="SelectPrinterNone(' + "\'" + strVendor + "\'" + ')">none</div>' +
				'	</div>' +
				'	<a>' + sVV + '</a>' +
				'</div>' +
				'<div class="PrinterArea"></div>' +
				'</div>';

			$('#PrinterGrid').append(HtmlNewVendor);
		}

		if (!ModelHtml.hasOwnProperty(strVendor))
			ModelHtml[strVendor] = '';

		let NozzleArray = OneModel['nozzle_diameter'].split(';');
		let HtmlNozzel = '';
		for (let m = 0; m < NozzleArray.length; m++) {
			let nNozzel = NozzleArray[m];
			HtmlNozzel += '<label class="pNozzel TextS2"><input type="checkbox" model="' + OneModel['model'] + '" nozzel="' + nNozzel + '" vendor="' + strVendor + '" onclick="CheckBoxOnclick(this)" /><span>' + nNozzel + '</span><span class="trans" tid="t13">mm nozzle</span></label>';
		}

		let CoverImage = OneModel['cover'];
		ModelHtml[strVendor] += '<div class="PrinterBlock">' +
			'	<div class="PImg"><img src="' + CoverImage + '"  /></div>' +
			'    <div class="PName">' + OneModel['name'] + '</div>' + HtmlNozzel + '</div>';
	}

	//Update Nozzle Html Append
	for (let key in ModelHtml) {
		$(".OneVendorBlock[vendor='" + key + "'] .PrinterArea").append(ModelHtml[key]);
	}

	// Re-apply vendor filter visibility
	let pVendor=$("#VendorFilterList input:not(#VendorAll)");
	for(let n=0;n<pVendor.length;n++)
	{
		let oneV=pVendor[n];
		let vName=oneV.getAttribute("vendorfilter");
		if(!oneV.checked)
			$(".OneVendorBlock[vendor='"+vName+"']").hide();
	}

	//Restore Checkbox state
	ModelSelect = $('input[type=checkbox][model]');
	for (let n = 0; n < ModelSelect.length; n++) {
		let OneItem = ModelSelect[n];
		OneItem.checked = GetModelSelect(OneItem.getAttribute("vendor"), OneItem.getAttribute("model"), OneItem.getAttribute("nozzel"));
	}

	TranslatePage();
}

function SelectPrinterAll( sVendor )
{
	$("input[vendor='"+sVendor+"'][model]").prop("checked", true);
	$("input[vendor='"+sVendor+"'][model]").each(function() {
		CheckBoxOnclick(this);
	});
}

function SelectPrinterNone( sVendor )
{
	$("input[vendor='"+sVendor+"'][model]").prop("checked", false);
	$("input[vendor='"+sVendor+"'][model]").each(function() {
		CheckBoxOnclick(this);
	});
}

function GotoFilamentPage()
{
	let nChoose=OnExitFilter();

	if(nChoose>0)
		window.open('../22/index.html','_self');
}

function OnExitFilter() {
	let nTotal = 0;
	let ModelAll = {};

	for (let vendor in ModelNozzleSelected) {
		for (let model in ModelNozzleSelected[vendor]) {
			for (let nozzel in ModelNozzleSelected[vendor][model]) {
				if (!ModelNozzleSelected[vendor][model][nozzel])
					continue;

				if (!ModelAll.hasOwnProperty(model)) {
					ModelAll[model] = {};
					ModelAll[model]["model"] = model;
					ModelAll[model]["nozzle_diameter"] = '';
					ModelAll[model]["vendor"] = vendor;
				}

				ModelAll[model]["nozzle_diameter"] += ModelAll[model]["nozzle_diameter"] == '' ? nozzel : ';' + nozzel;
				nTotal++;
			}
		}
	}

	if(nTotal == 0)
	{
		ShowNotice(1);
		return 0;
	}

	var tSend = {};
	tSend['sequence_id'] = Math.round(new Date() / 1000);
	tSend['command'] = "save_userguide_models";
	tSend['data'] = ModelAll;

	SendWXMessage(JSON.stringify(tSend));

	return nTotal;
}


function ShowNotice( nShow )
{
	if(nShow==0)
	{
		$("#NoticeMask").hide();
		$("#NoticeBody").hide();
	}
	else
	{
		$("#NoticeMask").show();
		$("#NoticeBody").show();
	}
}
