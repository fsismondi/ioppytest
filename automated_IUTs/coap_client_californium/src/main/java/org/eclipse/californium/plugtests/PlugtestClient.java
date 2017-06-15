/*******************************************************************************
 * Copyright (c) 2015 Institute for Pervasive Computing, ETH Zurich and others.
 * 
 * All rights reserved. This program and the accompanying materials
 * are made available under the terms of the Eclipse Public License v1.0
 * and Eclipse Distribution License v1.0 which accompany this distribution.
 * 
 * The Eclipse Public License is available at
 *    http://www.eclipse.org/legal/epl-v10.html
 * and the Eclipse Distribution License is available at
 *    http://www.eclipse.org/org/documents/edl-v10.html.
 * 
 * Contributors:
 *    Matthias Kovatsch - creator and main architect
 ******************************************************************************/
/**
 * 
 */
package org.eclipse.californium.plugtests;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Set;

import org.eclipse.californium.core.CoapClient;
import org.eclipse.californium.core.CoapHandler;
import org.eclipse.californium.core.CoapObserveRelation;
import org.eclipse.californium.core.CoapResponse;
import org.eclipse.californium.core.Utils;
import org.eclipse.californium.core.WebLink;
import org.eclipse.californium.core.coap.LinkFormat;
import org.eclipse.californium.core.coap.MediaTypeRegistry;
import org.eclipse.californium.core.coap.Request;
import org.eclipse.californium.core.network.EndpointManager;
import org.eclipse.californium.core.network.config.NetworkConfig;
import org.eclipse.californium.core.network.interceptors.MessageTracer;
import org.apache.commons.cli.*;

/**
 * The PlugtestClient uses the developer API of Californium to test
 * if the test cases can be implemented successfully.
 * This client does not implement the tests that are meant to check
 * the server functionality (e.g., stop Observe on DELETE).
 * 
 * Use this flag to customize logging output:
 * -Djava.util.logging.config.file=../run/Californium-logging.properties
 */
public class PlugtestClient {

	/**
	 * Main entry point.
	 * 
	 * @param args the arguments
	 */
	public static void main(String[] args) {
	
		Options options = new Options();

        Option skip = new Option("s", "skip", false, "Skip the ping in case the remote does not implement it");
        skip.setRequired(false);
        options.addOption(skip);

        Option uri = new Option("u", "URI", true, "The CoAP URI of the Plugtest server to test (coap://...)");
        uri.setRequired(false);
        options.addOption(uri);
        
        Option test_case = new Option("t", "test_case", true, "TD_COAP_CORE_XX, TD_COAP_LINK_XX, TD_COAP_BLOCK_XX, TD_COAP_OBS_XX The name of the test case that have to be executed");
        test_case.setRequired(true);
        options.addOption(test_case);

        CommandLineParser parser = new DefaultParser();
        HelpFormatter formatter = new HelpFormatter();
        CommandLine cmd;

        try {
            cmd = parser.parse(options, args);
        } catch (ParseException e) {
            System.out.println(e.getMessage());
            formatter.printHelp("utility-name", options);

            System.exit(1);
            return;
        }
        
        if (cmd.hasOption("skip")) {
        	String skipFilePath = cmd.getOptionValue("skip");
        }
        String uriFilePath = cmd.getOptionValue("URI");
        String test_case_name = cmd.getOptionValue("test_case");
        
     // Config used for plugtest
 		NetworkConfig.getStandard()
 			.setInt(NetworkConfig.Keys.MAX_MESSAGE_SIZE, 64)
 			.setInt(NetworkConfig.Keys.PREFERRED_BLOCK_SIZE, 64);
     		
     	System.out.println("uriFilePath "+uriFilePath);
     	
 		if (!uriFilePath.startsWith("coap://")) {
 			uriFilePath = "coap://" + uriFilePath;
 		}
 		if (uriFilePath.endsWith("/")) {
 			uriFilePath = uriFilePath.substring(-1);
 		}

 		if (cmd.hasOption("skip")) {
 			CoapClient clientPing = new CoapClient(uriFilePath);
 			System.out.println("===============\nCC31\n---------------");
 			if (!clientPing.ping(2000)) {
 				System.out.println(uriFilePath + " does not respond to ping, exiting...");
 				System.exit(-1);
 			} else {
 				System.out.println(uriFilePath + " reponds to ping");
 				
 				// add special interceptor for message traces
 	            EndpointManager.getEndpointManager().getDefaultEndpoint().addInterceptor(new MessageTracer());
 			}
 		}
 		
 		testCC(uriFilePath, test_case_name);
 		testCB(uriFilePath, test_case_name);
 		testCO(uriFilePath, test_case_name);
 		testCL(uriFilePath, test_case_name);
 		
 		
 		System.exit(0);
 	}
     	
 	public static void testCC(String uri, String test_case_name) {

 		// re-usable response object
 		CoapResponse response;
 		
 		CoapClient client = new CoapClient(uri + "/test");
 		if(test_case_name.equals("TD_COAP_CORE_01")) {
 			System.out.println("===============\nCC01");
 			System.out.println("---------------\nGET /test\n---------------");
 			response = client.get();
 			System.out.println(response.advanced().getType() + "-" + response.getCode());
 			System.out.println(response.getResponseText());
 			
 		}else if(test_case_name.equals("TD_COAP_CORE_02")){
 			System.out.println("===============\nCC02");
 			System.out.println("---------------\nDELETE /test\n---------------");
 			response = client.delete();
 			System.out.println(response.advanced().getType() + "-" + response.getCode());
 			System.out.println(response.getResponseText());
 			
 		}else if(test_case_name.equals("TD_COAP_CORE_03")){
 			System.out.println("===============\nCC03");
 			System.out.println("---------------\nPUT /test\n---------------");
 			response = client.put("", MediaTypeRegistry.TEXT_PLAIN);
 			System.out.println(response.advanced().getType() + "-" + response.getCode());
 			System.out.println(response.getResponseText());
 			
 		}else if(test_case_name.equals("TD_COAP_CORE_04")){
 			System.out.println("===============\nCC04");
 			System.out.println("---------------\nPOST /test\n---------------");
 			response = client.post("non-empty", MediaTypeRegistry.TEXT_PLAIN);
 			System.out.println(response.advanced().getType() + "-" + response.getCode());
 			System.out.println(response.getResponseText());
 			
 		}else if(test_case_name.equals("TD_COAP_CORE_05")){
 			client.useNONs();
 			System.out.println("===============\nCC05");
 			System.out.println("---------------\nNON-GET /test\n---------------");
 			response = client.get();
 			System.out.println(response.advanced().getType() + "-" + response.getCode());
 			System.out.println(response.getResponseText());
 			
 		}else if(test_case_name.equals("TD_COAP_CORE_06")){
 			client.useNONs();
 			System.out.println("===============\nCC06");
 			System.out.println("---------------\nNON-DELETE /test\n---------------");
 			response = client.delete();
 			System.out.println(response.advanced().getType() + "-" + response.getCode());
 			System.out.println(response.getResponseText());
 			
 		}else if(test_case_name.equals("TD_COAP_CORE_07")){
 			client.useNONs();
 			System.out.println("===============\nCC07");
 			System.out.println("---------------\nNON-PUT /test\n---------------");
 			response = client.put("", MediaTypeRegistry.TEXT_PLAIN);
 			System.out.println(response.advanced().getType() + "-" + response.getCode());
 			System.out.println(response.getResponseText());
 			
 		}else if(test_case_name.equals("TD_COAP_CORE_08")){
 			client.useNONs();
 			System.out.println("===============\nCC08");
 			System.out.println("---------------\nNON-POST /test\n---------------");
 			response = client.post("non-empty", MediaTypeRegistry.TEXT_PLAIN);
 			System.out.println(response.advanced().getType() + "-" + response.getCode());
 			System.out.println(response.getResponseText());
 			
 		}else if(test_case_name.equals("TD_COAP_CORE_09")){
 			client.setURI(uri + "/separate");
 			client.useCONs();
 			System.out.println("===============\nCC09");
 			System.out.println("---------------\nGET /separate\n---------------");
 			response = client.get();
 			System.out.println(response.advanced().getType() + "-" + response.getCode());
 			System.out.println(response.getResponseText());
 			
 		}else if(test_case_name.equals("TD_COAP_CORE_10")) {
 			System.out.println("===============\nCC10");
 			System.out.println("---------------\nGET /test\n---------------");
 			response = client.get();
 			System.out.println(response.advanced().getType() + "-" + response.getCode());
 			System.out.println(response.getResponseText());	
 			
 		}else if(test_case_name.equals("TD_COAP_CORE_11")){
 			client.setURI(uri + "/separate");
 			client.useCONs();
 			System.out.println("===============\nCC11");
 			System.out.println("---------------\nGET /separate\n---------------");
 			response = client.get();
 			System.out.println(response.advanced().getType() + "-" + response.getCode());
 			System.out.println(response.getResponseText());
 			
 		}else if(test_case_name.equals("TD_COAP_CORE_12")){
 			client.setURI(uri + "/test");

 			System.out.println("===============\nCC12");
 			System.out.println("---------------\nGET /test w/o Token\n---------------");
 			Request req12 = Request.newGet(); // never re-use a Request object
 			req12.setToken(new byte[0]);
 			response = client.advanced(req12);
 			System.out.println(response.advanced().getType() + "-" + response.getCode());
 			System.out.println(response.getResponseText());
 					
 		}else if(test_case_name.equals("TD_COAP_CORE_13")){
 			client.setURI(uri + "/seg1/seg2/seg3");

 			System.out.println("===============\nCC13");
 			System.out.println("---------------\nGET /seg1/seg2/seg3\n---------------");
 			response = client.get();
 			System.out.println(response.advanced().getType() + "-" + response.getCode());
 			System.out.println(response.getResponseText());
 			
 		}else if(test_case_name.equals("TD_COAP_CORE_14")){
 			client.setURI(uri + "/query?first=1&second=2");

 			System.out.println("===============\nCC14");
 			System.out.println("---------------\nGET /query?first=1&second=2\n---------------");
 			response = client.get();
 			System.out.println(response.advanced().getType() + "-" + response.getCode());
 			System.out.println(response.getResponseText());
 			
 		}else if(test_case_name.equals("TD_COAP_CORE_17")){
 			client.setURI(uri + "/separate");
 			client.setTimeout(10000);
 			client.useNONs();
 			
 			System.out.println("===============\nCC17");
 			System.out.println("---------------\nNON-GET /separate\n---------------");
 			response = client.get();
 			System.out.println(response.advanced().getType() + "-" + response.getCode());
 			System.out.println(response.getResponseText());
 			
 		}else if(test_case_name.equals("TD_COAP_CORE_18")){
 			client.setURI(uri + "/test");
 			client.setTimeout(0);
 			client.useCONs();
 			
 			System.out.println("===============\nCC18");
 			System.out.println("---------------\nPOST /test for Location-Path\n---------------");
 			response = client.post("TD_COAP_CORE_18", MediaTypeRegistry.TEXT_PLAIN);
 			System.out.println(response.getCode() + "-" + response.getOptions().getLocationString());
 			System.out.println(response.getResponseText());
 			
 		}else if(test_case_name.equals("TD_COAP_CORE_19")){
 			client.setURI(uri + "/location-query");
 			
 			System.out.println("===============\nCC19");
 			System.out.println("---------------\nGET /location-query\n---------------");
 			response = client.post("query", MediaTypeRegistry.TEXT_PLAIN);
 			System.out.println(response.getCode() + "-" + response.getOptions().getLocationString());
 			System.out.println(response.getResponseText());
 			
 		}else if(test_case_name.equals("TD_COAP_CORE_20")){
 			client.setURI(uri + "/multi-format");
 			
 			System.out.println("===============\nCC20");
 			System.out.println("---------------\nGET /multi-format text/plain\n---------------");
 			response = client.get(MediaTypeRegistry.TEXT_PLAIN);
 			System.out.println(response.getCode() + "-" + MediaTypeRegistry.toString(response.getOptions().getContentFormat()));
 			System.out.println(response.getResponseText());
 			System.out.println("---------------\nGET /multi-format application/xml\n---------------");
 			response = client.get(MediaTypeRegistry.APPLICATION_XML);
 			System.out.println(response.getCode() + "-" + MediaTypeRegistry.toString(response.getOptions().getContentFormat()));
 			System.out.println(response.getResponseText());
 			
 		}else if(test_case_name.equals("TD_COAP_CORE_21")){
 			client.setURI(uri + "/validate");
 			byte[] etag;
 			
 			System.out.println("===============\nCC21");
 			System.out.println("---------------\nGET /validate\n---------------");
 			response = client.get();
 			if (response.getOptions().getETagCount()==1) {
 				etag = response.getOptions().getETags().get(0);
 				System.out.println(response.getCode() + " - ETag [" + Utils.toHexString(etag) + "]");
 				System.out.println(response.getResponseText());

 				System.out.println("---------------\nGET /validate with ETag\n---------------");
 				response = client.validate(etag);
 				etag = response.getOptions().getETags().get(0);
 				System.out.println(response.getCode() + " - ETag [" + Utils.toHexString(etag) + "]");
 				System.out.println(response.getResponseText());

 				System.out.println("---------------\nPUT /validate stimulus\n---------------");
 				CoapClient clientStimulus = new CoapClient(uri + "/validate");
 				response = clientStimulus.put("CC21 at " + new SimpleDateFormat("HH:mm:ss.SSS").format(new Date()), MediaTypeRegistry.TEXT_PLAIN);
 				System.out.println(response.getCode());

 				System.out.println("---------------\nGET /validate with ETag\n---------------");
 				response = client.validate(etag);
 				etag = response.getOptions().getETags().get(0);
 				System.out.println(response.getCode() + " - ETag [" + Utils.toHexString(etag) + "]");
 				System.out.println(response.getResponseText());
 				
 			} else {
 				System.out.println("Error - no ETag");
 			}
 			
 		}else if(test_case_name.equals("TD_COAP_CORE_22")){
 			client.setURI(uri + "/validate");
 			byte[] etag;
 			System.out.println("===============\nCC22");
 			System.out.println("---------------\nGET /validate with If-Match\n---------------");
 			response = client.get();
 			if (response.getOptions().getETagCount()==1) {
 				etag = response.getOptions().getETags().get(0);
 				System.out.println(response.getCode() + " - ETag [" + Utils.toHexString(etag) + "]");
 				System.out.println(response.getResponseText());

 				System.out.println("---------------\nPUT /validate If-Match [" + Utils.toHexString(etag) + "]\n---------------");
 				response = client.putIfMatch("CC22 at " + new SimpleDateFormat("HH:mm:ss.SSS").format(new Date()),
 						MediaTypeRegistry.TEXT_PLAIN, etag);
 				System.out.println(response.getCode());

 				System.out.println("---------------\nGET /validate\n---------------");
 				response = client.get();
 				etag = response.getOptions().getETags().get(0);
 				System.out.println(response.getCode() + " - ETag [" + Utils.toHexString(etag) + "]");
 				System.out.println(response.getResponseText());
 				
 				System.out.println("---------------\nPUT /validate stimulus\n---------------");
 				CoapClient clientStimulus = new CoapClient(uri + "/validate");
 				response = clientStimulus.put("CC22 at " + new SimpleDateFormat("HH:mm:ss.SSS").format(new Date()), MediaTypeRegistry.TEXT_PLAIN);
 				System.out.println(response.getCode());
 				
 				System.out.println("---------------\nPUT /validate If-Match [" + Utils.toHexString(etag) + "]\n---------------");
 				response = client.putIfMatch("CC22 at " + new SimpleDateFormat("HH:mm:ss.SSS").format(new Date()),
 						MediaTypeRegistry.TEXT_PLAIN, etag);
 				System.out.println(response.getCode());
 				
 			} else {
 				System.out.println("Error - no ETag");
 			}
 			
 		}else if(test_case_name.equals("TD_COAP_CORE_23")){
 			client.setURI(uri + "/create1");
 			
 			System.out.println("===============\nCC23");
 			System.out.println("---------------\nPUT /create1 with If-None-Match\n---------------");
 			response = client.putIfNoneMatch("CC23 at " + new SimpleDateFormat("HH:mm:ss.SSS").format(new Date()),
 					MediaTypeRegistry.TEXT_PLAIN);
 			System.out.println(response.getCode());
 			System.out.println("---------------\nPUT /create1 with If-None-Match\n---------------");
 			response = client.putIfNoneMatch("CC23 at " + new SimpleDateFormat("HH:mm:ss.SSS").format(new Date()),
 					MediaTypeRegistry.TEXT_PLAIN);
 			System.out.println(response.getCode());
 			
 		}
 	
 	}
 	
	public static void testCL(String uri, String test_case_name) {

		CoapClient client = new CoapClient(uri);
		Set<WebLink> links;
		
		if(test_case_name.equals("TD_COAP_LINK_01")){
			System.out.println("===============\nCL01");
			System.out.println("---------------\nGET /.well-known/core\n---------------");
			links = client.discover();
			for (WebLink link : links) {
				System.out.println(link);
			}
			
		}else if(test_case_name.equals("TD_COAP_LINK_02")){
			System.out.println("===============\nCL02");
			System.out.println("---------------\nGET /.well-known/core?rt=Type1\n---------------");
			links = client.discover("rt=Type1");
			for (WebLink link : links) {
				System.out.println(link);
			}
			
		}else if(test_case_name.equals("TD_COAP_LINK_03")){
			System.out.println("===============\nCL03");
			System.out.println("---------------\nGET /.well-known/core?rt=*\n---------------");
			links = client.discover("rt=*");
			for (WebLink link : links) {
				System.out.println(link);
			}
			
		}else if(test_case_name.equals("TD_COAP_LINK_04")){
			System.out.println("===============\nCL04");
			System.out.println("---------------\nGET /.well-known/core?rt=Type2\n---------------");
			links = client.discover("rt=Type2");
			for (WebLink link : links) {
				System.out.println(link);
			}
			
		}else if(test_case_name.equals("TD_COAP_LINK_05")){
			System.out.println("===============\nCL05");
			System.out.println("---------------\nGET /.well-known/core?if=If*\n---------------");
			links = client.discover("if=If*");
			for (WebLink link : links) {
				System.out.println(link);
			}
			
		}else if(test_case_name.equals("TD_COAP_LINK_06")){
			System.out.println("===============\nCL06");
			System.out.println("---------------\nGET /.well-known/core?sz=*\n---------------");
			links = client.discover("sz=*");
			for (WebLink link : links) {
				System.out.println(link);
			}
			
		}else if(test_case_name.equals("TD_COAP_LINK_07")){
			System.out.println("===============\nCL07");
			System.out.println("---------------\nGET /.well-known/core?href=/link1\n---------------");
			links = client.discover("href=/link1");
			for (WebLink link : links) {
				System.out.println(link);
			}
			
		}else if(test_case_name.equals("TD_COAP_LINK_08")){
			System.out.println("===============\nCL08");
			System.out.println("---------------\nGET /.well-known/core?href=/link*\n---------------");
			links = client.discover("href=/link*");
			for (WebLink link : links) {
				System.out.println(link);
			}
			
		}else if(test_case_name.equals("TD_COAP_LINK_09")){
			System.out.println("===============\nCL09");
			System.out.println("---------------\nGET /.well-known/core?ct=40\n---------------");
			links = client.discover("ct=40");
			System.out.println("Found " + links.size() + " resource(s)");
			for (WebLink link : links) {
				client.setURI(link.getURI());
				System.out.println("---------------\nGET " + link.getURI() + " with ct=40\n---------------");
				Set<WebLink> links2 = LinkFormat.parse(client.get(MediaTypeRegistry.APPLICATION_LINK_FORMAT).getResponseText());
				System.out.println("Found " + links2.size() + " resource(s)");
				for (WebLink link2 : links2) {
					client.setURI(link2.getURI());
					System.out.println("---------------\nGET " + link2.getURI() + "\n---------------");
					CoapResponse response = client.get();
					System.out.println(response.advanced().getType() + "-" + response.getCode());
					System.out.println(response.getResponseText());
				}
			}
		}
	}	
	
	public static void testCB(String uri, String test_case_name) {
		
		CoapClient client = new CoapClient(uri + "/large");
		CoapResponse response;
		if(test_case_name.equals("TD_COAP_BLOCK_01")){
			client.setURI(uri + "/large");
			client.useEarlyNegotiation(64);
			
			System.out.println("===============\nCB01");
			System.out.println("---------------\nGET /large\n---------------");
			response = client.get();
			System.out.println(response.getCode());
			System.out.println(response.getResponseText());
			
		}else if(test_case_name.equals("TD_COAP_BLOCK_02")){
			client.setURI(uri + "/large");
			client.useLateNegotiation();

			System.out.println("===============\nCB02");
			System.out.println("---------------\nGET /large\n---------------");
			response = client.get();
			System.out.println(response.getCode());
			System.out.println(response.getResponseText());
			
		}else if(test_case_name.equals("TD_COAP_BLOCK_03")){
			client.setURI(uri + "/large-update");

			System.out.println("===============\nCB03");
			System.out.println("---------------\nPUT /large-update\n---------------");
			response = client.put(getLargeRequestPayload(), MediaTypeRegistry.TEXT_PLAIN);
			System.out.println(response.getCode());
			System.out.println(response.getResponseText());
			
		}else if(test_case_name.equals("TD_COAP_BLOCK_04")){
			client.setURI(uri + "/large-create");

			System.out.println("===============\nCB04");
			System.out.println("---------------\nPOST /large-create\n---------------");
			response = client.post(getLargeRequestPayload(), MediaTypeRegistry.TEXT_PLAIN);
			System.out.println(response.getCode() + " - " + response.getOptions().getLocationString());
			System.out.println(response.getResponseText());

			client.setURI(uri + response.getOptions().getLocationString());

			System.out.println("---------------\nGET " + response.getOptions().getLocationString() + "\n---------------");
			response = client.get();
			System.out.println(response.getCode());
			System.out.println(response.getResponseText());
			
		}else if(test_case_name.equals("TD_COAP_BLOCK_05")){
			client.setURI(uri + "/large-post");

			System.out.println("===============\nCB05");
			System.out.println("---------------\nPOST /large-post\n---------------");
			response = client.post(getLargeRequestPayload(), MediaTypeRegistry.TEXT_PLAIN);
			System.out.println(response.getCode());
			System.out.println(response.getResponseText());
			
		}else if(test_case_name.equals("TD_COAP_BLOCK_06")){
			client.setURI(uri + "/large");
			client.useEarlyNegotiation(16);
			
			System.out.println("===============\nCB06");
			System.out.println("---------------\nGET /large\n---------------");
			response = client.get();
			System.out.println(response.getCode());
			System.out.println(response.getResponseText());
			
		}
	}

	public static void testCO(String uri, String test_case_name) {
		
		CoapClient client = new CoapClient(uri + "/obs");
		
		if(test_case_name.equals("TD_COAP_OBS_01")){
			System.out.println("===============\nCO01+06");
			System.out.println("---------------\nGET /obs with Observe");
			CoapObserveRelation relation1 = client.observe(
					new CoapHandler() {
						@Override public void onLoad(CoapResponse response) {
							String content = response.getResponseText();
							System.out.println("-CO01----------");
							System.out.println(content);
						}
						
						@Override public void onError() {
							System.err.println("-Failed--------");
						}
					});
			try { Thread.sleep(6*1000); } catch (InterruptedException e) { }
			System.out.println("---------------\nCancel Observe");
			relation1.reactiveCancel();
			try { Thread.sleep(6*1000); } catch (InterruptedException e) { }
			
		}else if(test_case_name.equals("TD_COAP_OBS_02")){
			client.setURI(uri + "/obs-non").useNONs();
			
			System.out.println("===============\nCO02+06");
			System.out.println("---------------\nNON-GET /obs-non with Observe");
			CoapObserveRelation relation2 = client.observe(
					new CoapHandler() {
						@Override public void onLoad(CoapResponse response) {
							String content = response.getResponseText();
							System.out.println("-CO02----------");
							System.out.println(content);
						}
						
						@Override public void onError() {
							System.err.println("-Failed--------");
						}
					});
			try { Thread.sleep(6*1000); } catch (InterruptedException e) { }
			System.out.println("---------------\nCancel Observe");
			relation2.proactiveCancel();
			try { Thread.sleep(2*1000); } catch (InterruptedException e) { }
			
		}else if(test_case_name.equals("TD_COAP_OBS_04")){
			client.setURI(uri + "/obs").useCONs();
			
			System.out.println("===============\nCO04");
			System.out.println("---------------\nGET /obs with Observe");
			CoapObserveRelation relation4 = client.observeAndWait(
					new CoapHandler() {
						@Override public void onLoad(CoapResponse response) {
							String content = response.getResponseText();
							System.out.println("-CO04----------");
							System.out.println(content);
						}
						
						@Override public void onError() {
							System.err.println("-Failed--------");
						}
					});
			long timeout = relation4.getCurrent().getOptions().getMaxAge();
			try { Thread.sleep(6*1000); } catch (InterruptedException e) { }
			System.out.println("---------------\nReboot Server");
			CoapClient clientStimulus = new CoapClient(uri + "/obs-reset");
			clientStimulus.post("sesame", MediaTypeRegistry.TEXT_PLAIN);
			try { Thread.sleep((timeout+6)*1000); } catch (InterruptedException e) { }
			relation4.proactiveCancel();
			try { Thread.sleep(2*1000); } catch (InterruptedException e) { }
			
		}else if(test_case_name.equals("TD_COAP_OBS_13")){
			client.setURI(uri + "/obs-large");

			System.out.println("===============\nCO13");
			System.out.println("---------------\nGET /obs-large with Observe");
			CoapObserveRelation relation13 = client.observe(
					new CoapHandler() {
						@Override public void onLoad(CoapResponse response) {
							String content = response.getResponseText();
							System.out.println("-CO13----------");
							System.out.println(content);
						}
						
						@Override public void onError() {
							System.err.println("-Failed--------");
						}
					});
			try { Thread.sleep(11*1000); } catch (InterruptedException e) { }
			System.out.println("---------------\nCancel Observe");
			relation13.proactiveCancel();
			try { Thread.sleep(6*1000); } catch (InterruptedException e) { }
			
		}else if(test_case_name.equals("TD_COAP_OBS_14")){
			client.setURI(uri + "/obs-pumping");

			System.out.println("===============\nCO14");
			System.out.println("---------------\nGET /obs-pumping with Observe");
			CoapObserveRelation relation14 = client.observe(
					new CoapHandler() {
						@Override public void onLoad(CoapResponse response) {
							String content = response.getResponseText();
							System.out.println("-CO14----------");
							System.out.println(content);
						}
						
						@Override public void onError() {
							System.err.println("-Failed--------");
						}
					});
			try { Thread.sleep(21*1000); } catch (InterruptedException e) { }
			System.out.println("---------------\nCancel Observe");
			relation14.proactiveCancel();
			try { Thread.sleep(6*1000); } catch (InterruptedException e) { }
			
		}
	}



	public static String getLargeRequestPayload() {
		return new StringBuilder()
				.append("/-------------------------------------------------------------\\\n")
				.append("|                  Request BLOCK NO. 1 OF 5                   |\n")
				.append("|               [each line contains 64 bytes]                 |\n")
				.append("\\-------------------------------------------------------------/\n")
				.append("/-------------------------------------------------------------\\\n")
				.append("|                  Request BLOCK NO. 2 OF 5                   |\n")
				.append("|               [each line contains 64 bytes]                 |\n")
				.append("\\-------------------------------------------------------------/\n")
				.append("/-------------------------------------------------------------\\\n")
				.append("|                  Request BLOCK NO. 3 OF 5                   |\n")
				.append("|               [each line contains 64 bytes]                 |\n")
				.append("\\-------------------------------------------------------------/\n")
				.append("/-------------------------------------------------------------\\\n")
				.append("|                  Request BLOCK NO. 4 OF 5                   |\n")
				.append("|               [each line contains 64 bytes]                 |\n")
				.append("\\-------------------------------------------------------------/\n")
				.append("/-------------------------------------------------------------\\\n")
				.append("|                  Request BLOCK NO. 5 OF 5                   |\n")
				.append("|               [each line contains 64 bytes]                 |\n")
				.append("\\-------------------------------------------------------------/\n")
				.toString();
	}
}
